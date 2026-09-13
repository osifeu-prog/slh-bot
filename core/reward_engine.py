"""SLH Reward Engine.

Staking rewards are accrued as pending pool entries and settled through the
Economy Authority. Settlement is cumulative and idempotent per position.
"""

from datetime import datetime
import json
import time
from pathlib import Path

import state_manager
from core import economy_service
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
        result["credits"] = economy_service.record_transaction(
            uid=uid,
            amount=credits,
            reason=reason,
            meta={"idempotency_key": key},
        )
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
    """Record the cumulative accrued reward and current pending amount."""
    def mutate(db):
        pos = db.get("stake_positions", {}).get(position_id)
        if not pos:
            raise KeyError("position not found")
        created = pos.get("created_at", time.time())
        days = max(0, (time.time() - created) / 86400)
        gross = round(float(pos["amount"]) * days * rate_per_day, 6)
        pools = db.setdefault("reward_pools", {})
        previous = pools.get(position_id, {})
        settled_total = round(float(previous.get("settled_total", 0) or 0), 6)
        pending = max(0, round(gross - settled_total, 6))
        pools[position_id] = {
            "position_id": position_id,
            "reward": pending,
            "accrued_total": gross,
            "settled_total": settled_total,
            "calculated_at": time.time(),
            "status": "pending" if pending > 0 else "settled",
        }
        return pending

    return state_manager.atomic_update(mutate)


def settle(position_id, rate_per_day=0.001333):
    """Settle all currently earned but unsettled reward for a stake position.

    The Economy Authority performs the wallet mutation, idempotency check,
    reward-pool update, and ledger append in one atomic DB transaction.
    """
    db = _load_db()
    pos = db.get("stake_positions", {}).get(position_id)
    if not pos:
        raise KeyError("position not found")

    uid = str(pos.get("uid"))
    if not uid or uid == "None":
        raise ValueError("position owner missing")

    created = pos.get("created_at", time.time())
    days = max(0, (time.time() - created) / 86400)
    gross = round(float(pos["amount"]) * days * rate_per_day, 6)
    pool = db.get("reward_pools", {}).get(position_id, {})
    settled_total = round(float(pool.get("settled_total", 0) or 0), 6)
    pending = max(0, round(gross - settled_total, 6))

    return economy_service.settle_staking_reward(
        uid=uid,
        position_id=str(position_id),
        amount=pending,
        accrued_total=gross,
        reason="staking:reward_settlement",
        meta={"rate_per_day": rate_per_day},
    )
