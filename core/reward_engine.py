"""
SLH Reward Engine
Single reward gateway + staking reward calculator.
"""

from datetime import datetime
from core import economy_bridge
from core import profile_manager
import json, time
from pathlib import Path


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
        result["credits"] = economy_bridge.add_credits(
            uid, credits, reason=reason, meta={"idempotency_key": key}
        )
    if points:
        profile_manager.add_points(
            uid, points, reason=reason, meta={"idempotency_key": key}
        )
        result["points"] = points

    entry = {
        "user": str(uid),
        "reason": reason,
        "credits": credits,
        "points": points,
        "timestamp": datetime.utcnow().isoformat(),
    }
    ledger = _load()
    ledger.append(entry)
    _save(ledger)
    return result


def _load_db():
    return json.loads(Path("state/db.json").read_text(encoding="utf-8"))


def calculate_reward(position_id, rate_per_day=0.0005):
    db = _load_db()
    pos = db.get("stake_positions", {}).get(position_id)
    if not pos:
        raise KeyError("position not found")
    created = pos.get("created_at", time.time())
    days = max(0, (time.time() - created) / 86400)
    return round(float(pos["amount"]) * days * rate_per_day, 6)


def accrue(position_id, rate_per_day=0.0005):
    reward = calculate_reward(position_id, rate_per_day)
    db = _load_db()
    pools = db.setdefault("reward_pools", {})
    pools[position_id] = {
        "position_id": position_id,
        "reward": reward,
        "calculated_at": time.time(),
        "status": "pending",
    }
    Path("state/db.json").write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    return reward
