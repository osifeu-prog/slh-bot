"""SLH Reward Engine.

Credits are issued through the Economy Authority. Reward-pool bookkeeping is
lock-safe and cumulative so a position can receive multiple reward settlements.
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
    if pos.get("status") == "unlocked":
        return 0.0
    created = pos.get("created_at", time.time())
    days = max(0, (time.time() - created) / 86400)
    gross = round(float(pos["amount"]) * days * rate_per_day, 6)
    pool = db.get("reward_pools", {}).get(position_id, {})
    settled_total = round(float(pool.get("settled_total", 0) or 0), 6)
    return max(0, round(gross - settled_total, 6))


def accrue(position_id, rate_per_day=0.001333):
    def mutate(db):
        pos = db.get("stake_positions", {}).get(position_id)
        if not pos:
            raise KeyError("position not found")
        if pos.get("status") == "unlocked":
            return {"position_id": position_id, "reward": 0.0, "status": "closed"}
        created = pos.get("created_at", time.time())
        days = max(0, (time.time() - created) / 86400)
        gross = round(float(pos["amount"]) * days * rate_per_day, 6)
        pools = db.setdefault("reward_pools", {})
        existing = pools.get(position_id, {})
        settled_total = round(float(existing.get("settled_total", 0) or 0), 6)
        reward = max(0, round(gross - settled_total, 6))
        entry = {
            "position_id": str(position_id),
            "uid": str(pos.get("uid")),
            "reward": reward,
            "accrued_total": gross,
            "settled_total": settled_total,
            "asset": "credits",
            "rate_per_day": float(rate_per_day),
            "calculated_at": time.time(),
            "status": "pending" if reward > 0 else "settled",
        }
        pools[position_id] = entry
        return dict(entry)

    return state_manager.atomic_update(mutate)


def claim_reward(position_id, idempotency_key=None):
    """Settle one pending reward snapshot through the Economy Authority.

    The idempotency key is derived from the reward snapshot unless explicitly
    supplied. Each new accrual therefore gets a new key, while retries of the
    same snapshot remain safe.
    """
    position_id = str(position_id)
    db = state_manager.load_db()
    pos = db.get("stake_positions", {}).get(position_id)
    if not pos:
        raise KeyError("position not found")
    if pos.get("status") == "unlocked":
        return {"status": "closed", "position_id": position_id}

    pool = db.get("reward_pools", {}).get(position_id)
    if not pool:
        raise ValueError("reward not accrued")
    if pool.get("status") == "paid" and not pool.get("reward"):
        return {"status": "already_paid", **pool}
    if pool.get("status") not in {"pending", "paid"}:
        raise ValueError("reward is not claimable")

    amount = round(float(pool.get("reward", 0) or 0), 6)
    if amount <= 0:
        return {"status": "nothing_to_claim", **pool}

    uid = str(pos.get("uid"))
    if not uid or uid == "None":
        raise ValueError("position owner missing")

    key = str(idempotency_key or (
        f"staking-reward:{position_id}:"
        f"{pool.get('calculated_at')}:{pool.get('accrued_total')}"
    )).strip()
    if not key:
        raise ValueError("idempotency_key required")

    after = economy_bridge.add_credits(
        uid,
        amount,
        reason="staking:reward_claim",
        meta={
            "idempotency_key": key,
            "position_id": position_id,
            "asset": "credits",
            "accrued_total": pool.get("accrued_total"),
        },
    )

    def finalize(db2):
        pools = db2.setdefault("reward_pools", {})
        current = pools.get(position_id)
        if not current:
            raise KeyError("reward pool missing")

        current_settled = round(float(current.get("settled_total", 0) or 0), 6)
        snapshot_total = round(float(pool.get("accrued_total", 0) or 0), 6)
        current_settled = max(current_settled, snapshot_total)
        current_accrued = round(float(current.get("accrued_total", 0) or 0), 6)
        current["settled_total"] = current_settled
        current["reward"] = max(0, round(current_accrued - current_settled, 6))
        current["status"] = "pending" if current["reward"] > 0 else "settled"
        current["paid_amount"] = amount
        current["paid_at"] = datetime.utcnow().isoformat()
        current["claim_idempotency_key"] = key

        transactions = db2.setdefault("reward_transactions", [])
        if not any(str(tx.get("idempotency_key")) == key for tx in transactions):
            transactions.append({
                "idempotency_key": key,
                "position_id": position_id,
                "uid": uid,
                "asset": "credits",
                "amount": amount,
                "after": after,
                "reason": "staking:reward_claim",
                "timestamp": datetime.utcnow().isoformat(),
            })

        return {
            "status": "paid" if current["reward"] == 0 else "paid_partial",
            "position_id": position_id,
            "amount": amount,
            "after": after,
        }

    return state_manager.atomic_update(finalize)


def get_reward_status(position_id):
    position_id = str(position_id)
    db = state_manager.load_db()
    pool = db.get("reward_pools", {}).get(position_id)
    if not pool:
        return {"status": "not_accrued", "position_id": position_id}
    return dict(pool)
