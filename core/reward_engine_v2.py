"""Atomic staking reward settlement helpers.

Alpha-ready Credits reward settlement. The canonical DB is the source of truth:
reward-pool state, wallet mutation, and reward transaction ledger are committed
in one state_manager.atomic_update.
"""

import time
from datetime import datetime, timezone

import state_manager

DEFAULT_RATE_PER_DAY = 0.001333
REWARD_POOLS_KEY = "reward_pools"
REWARD_TX_KEY = "reward_transactions"


def calculate_reward(position_id, rate_per_day=DEFAULT_RATE_PER_DAY):
    db = state_manager.load_db()
    pos = db.get("stake_positions", {}).get(str(position_id))
    if not pos:
        raise KeyError("position not found")
    if pos.get("status") == "unlocked":
        return 0.0
    created = float(pos.get("created_at", time.time()))
    days = max(0.0, (time.time() - created) / 86400.0)
    return round(float(pos.get("amount", 0) or 0) * days * float(rate_per_day), 6)


def accrue(position_id, rate_per_day=DEFAULT_RATE_PER_DAY):
    position_id = str(position_id)

    def mutate(db):
        pos = db.get("stake_positions", {}).get(position_id)
        if not pos:
            raise KeyError("position not found")
        if pos.get("status") == "unlocked":
            return {"position_id": position_id, "reward": 0.0, "status": "closed"}
        created = float(pos.get("created_at", time.time()))
        days = max(0.0, (time.time() - created) / 86400.0)
        reward = round(float(pos.get("amount", 0) or 0) * days * float(rate_per_day), 6)
        pools = db.setdefault(REWARD_POOLS_KEY, {})
        existing = pools.get(position_id)
        if existing and existing.get("status") == "paid":
            return dict(existing)
        entry = {
            "position_id": position_id,
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
    """Claim a pending staking reward exactly once."""
    position_id = str(position_id)
    key = str(idempotency_key or f"staking-reward:{position_id}").strip()
    if not key:
        raise ValueError("idempotency_key required")

    def mutate(db):
        pos = db.get("stake_positions", {}).get(position_id)
        if not pos:
            raise KeyError("position not found")
        pool = db.setdefault(REWARD_POOLS_KEY, {}).get(position_id)
        if not pool:
            raise ValueError("reward not accrued")
        transactions = db.setdefault(REWARD_TX_KEY, [])
        for tx in transactions:
            if str(tx.get("idempotency_key")) == key:
                return {"status": "duplicate", **tx}
        if pool.get("status") == "paid":
            return {"status": "already_paid", **pool}
        if pool.get("status") != "pending":
            raise ValueError("reward is not claimable")
        amount = round(float(pool.get("reward", 0) or 0), 6)
        if amount <= 0:
            raise ValueError("reward is zero")
        uid = str(pos.get("uid"))
        user = db.setdefault("users", {}).get(uid)
        if user is None:
            raise ValueError("user not found")
        wallet = user.setdefault("wallet", {})
        before = float(wallet.get("credits", 0) or 0)
        after = before + amount
        wallet["credits"] = after
        now = datetime.now(timezone.utc).isoformat()
        tx = {
            "idempotency_key": key,
            "position_id": position_id,
            "uid": uid,
            "asset": "credits",
            "amount": amount,
            "before": before,
            "after": after,
            "reason": "staking:reward_claim",
            "timestamp": now,
        }
        transactions.append(tx)
        db.setdefault("ledger", []).append({
            "time": now,
            "uid": uid,
            "before": before,
            "amount": amount,
            "after": after,
            "reason": "staking:reward_claim",
            "meta": {"position_id": position_id, "idempotency_key": key, "asset": "credits"},
        })
        pool["status"] = "paid"
        pool["paid_at"] = now
        pool["paid_amount"] = amount
        pool["claim_idempotency_key"] = key
        return {"status": "paid", **tx}

    return state_manager.atomic_update(mutate)


def get_reward_status(position_id):
    position_id = str(position_id)
    db = state_manager.load_db()
    pool = db.get(REWARD_POOLS_KEY, {}).get(position_id)
    if not pool:
        return {"status": "not_accrued", "position_id": position_id}
    return dict(pool)
