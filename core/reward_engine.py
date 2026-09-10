"""SLH Reward Engine.

Credits are issued through the Economy Authority. Reward-pool bookkeeping is
kept lock-safe so a concurrent wallet update cannot be overwritten by a stale
snapshot.
"""

from datetime import datetime
import json
import time
from pathlib import Path

import state_manager
from core import economy_bridge
from core import profile_manager

LEDGER = Path("state/rewards_ledger.json")


def _load():
    if not LEDGER.exists():
        return []
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(data):
    LEDGER.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def grant(uid, reason, credits=0, points=0, idempotency_key=None):
    if not uid:
        raise ValueError("Reward requires user id")
    if not reason:
        raise ValueError("Reward requires reason")
    if credits == 0 and points == 0:
        raise ValueError("Empty reward rejected")

    key = idempotency_key or f"{uid}:{reason}"
    result = {}
    if credits:
        result["credits"] = economy_bridge.add_credits(uid, credits, reason=reason, meta={"idempotency_key": key})
    if points:
        profile_manager.add_points(uid, points, reason=reason, meta={"idempotency_key": key})
        result["points"] = points

    entry = {
        "user": str(uid),
        "reason": reason,
        "credits": credits,
        "points": points,
        "timestamp": datetime.utcnow().isoformat(),
        "idempotency_key": key,
    }
    ledger = _load()
    if not any(str(x.get("idempotency_key", "")) == key for x in ledger):
        ledger.append(entry)
        try:
            _save(ledger)
        except Exception as exc:
            result["ledger_warning"] = type(exc).__name__
    return result


def _load_db():
    return state_manager.load_db()


def calculate_reward(position_id, rate_per_day=0.001333):
    db = _load_db()
    pos = db.get("stake_positions", {}).get(position_id)
    if not pos:
        raise KeyError("position not found")
    created = pos.get("created_at", time.time())
    days = max(0, (time.time() - created) / 86400)
    return round(float(pos["amount"]) * days * rate_per_day, 6)


def accrue(position_id, rate_per_day=0.001333):
    def mutate(db):
        pos = db.get("stake_positions", {}).get(position_id)
        if not pos:
            raise KeyError("position not found")
        created = pos.get("created_at", time.time())
        days = max(0, (time.time() - created) / 86400)
        reward = round(float(pos["amount"]) * days * rate_per_day, 6)
        pools = db.setdefault("reward_pools", {})
        pools[position_id] = {
            "position_id": position_id,
            "reward": reward,
            "calculated_at": time.time(),
            "status": "pending",
        }
        return reward

    return state_manager.atomic_update(mutate)
