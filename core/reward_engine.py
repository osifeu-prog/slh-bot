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
    if pos.get("status") == "unlocked":
        return 0.0
    created = pos.get("created_at", time.time())
    days = max(0, (time.time() - created) / 86400)
    return round(float(pos["amount"]) * days * rate_per_day, 6)


def accrue(position_id, rate_per_day=0.001333):
    def mutate(db):
        pos = db.get("stake_positions", {}).get(position_id)
        if not pos:
            raise KeyError("position not found")
        if pos.get("status") == "unlocked":
            return {"position_id": position_id, "reward": 0.0, "status": "closed"}
        created = pos.get("created_at", time.time())
        days = max(0, (time.time() - created) / 86400)
        reward = round(float(pos["amount"]) * days * rate_per_day, 6)
        pools = db.setdefault("reward_pools", {})
        existing = pools.get(position_id)
        if existing and existing.get("status") == "paid":
            return dict(existing)
        entry = {
            "position_id": str(position_id),
            "uid": str(pos.get("uid")),
            "reward": reward,
            "asset": "credits",
            "rate_per_day": float(rate_per_day),
            "calculated_at": time.time(),
            "status": "pending",
        }
        pools[position_id] = entry
        return dict(entry)

    return state_manager.atomic_update(mutate)


def claim_reward(position_id, idempotency_key=None):
    """Settle one accrued staking reward through the Economy Authority.

    The wallet mutation is delegated to economy_bridge/economy_service, never
    performed directly here. Settlement is intentionally two-phase because
    economy_service owns its own atomic DB transaction: the deterministic
    idempotency key makes retries safe if the process stops between the credit
    and reward-pool bookkeeping phases.
    """
    position_id = str(position_id)
    key = str(idempotency_key or f"staking-reward:{position_id}").strip()
    if not key:
        raise ValueError("idempotency_key required")

    db = state_manager.load_db()
    pos = db.get("stake_positions", {}).get(position_id)
    if not pos:
        raise KeyError("position not found")
    pool = db.get("reward_pools", {}).get(position_id)
    if not pool:
        raise ValueError("reward not accrued")
    if pool.get("status") == "paid":
        return {"status": "already_paid", **pool}
    if pool.get("status") != "pending":
        raise ValueError("reward is not claimable")

    amount = round(float(pool.get("reward", 0) or 0), 6)
    if amount <= 0:
        raise ValueError("reward is zero")
    uid = str(pos.get("uid"))

    # Canonical wallet mutation. economy_service.record_transaction() is
    # idempotent on this key, so a retry after a partial failure cannot double
    # credit the user.
    after = economy_bridge.add_credits(
        uid,
        amount,
        reason="staking:reward_claim",
        meta={"idempotency_key": key, "position_id": position_id, "asset": "credits"},
    )

    def finalize(db2):
        pools = db2.setdefault("reward_pools", {})
        current = pools.get(position_id)
        if current and current.get("status") == "paid":
            return {"status": "already_paid", **current}

        transactions = db2.setdefault("reward_transactions", [])
        for tx in transactions:
            if str(tx.get("idempotency_key")) == key:
                return {"status": "duplicate", **tx}

        now = datetime.utcnow().isoformat()
        tx = {
            "idempotency_key": key,
            "position_id": position_id,
            "uid": uid,
            "asset": "credits",
            "amount": amount,
            "after": after,
            "reason": "staking:reward_claim",
            "timestamp": now,
        }
        transactions.append(tx)
        current = current or {
            "position_id": position_id,
            "uid": uid,
            "reward": amount,
            "asset": "credits",
        }
        current["status"] = "paid"
        current["paid_at"] = now
        current["paid_amount"] = amount
        current["claim_idempotency_key"] = key
        pools[position_id] = current
        return {"status": "paid", **tx}

    return state_manager.atomic_update(finalize)


def get_reward_status(position_id):
    position_id = str(position_id)
    db = state_manager.load_db()
    pool = db.get("reward_pools", {}).get(position_id)
    if not pool:
        return {"status": "not_accrued", "position_id": position_id}
    return dict(pool)
