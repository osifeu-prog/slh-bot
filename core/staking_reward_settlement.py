"""Staking reward settlement boundary.

The Economy Authority remains the only wallet-credit mutation path. Reward pool
state is committed separately but is recoverable because settlement uses a
stable idempotency key derived from the pending pool snapshot.
"""

import time

import state_manager
from core import economy_service

RATE_PER_DAY = 0.001333


def settle_position_reward(position_id, rate_per_day=RATE_PER_DAY):
    """Accrue and settle the current pending reward exactly once.

    A pending pool snapshot supplies a stable settlement key. If the process
    fails after the wallet transaction but before the pool is marked settled,
    retrying the same snapshot is a no-op at the Economy Authority and then
    completes the pool state transition.
    """
    position_id = str(position_id)
    if not position_id:
        raise ValueError("position_id required")

    def accrue(db):
        pos = db.get("stake_positions", {}).get(position_id)
        if not pos:
            raise KeyError("position not found")
        created = float(pos.get("created_at", time.time()))
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
        return dict(pools[position_id]), str(pos.get("uid"))

    pool, uid = state_manager.atomic_update(accrue)
    pending = float(pool.get("reward", 0) or 0)
    if pending <= 0:
        return {
            "status": "nothing_to_settle",
            "position_id": position_id,
            "amount": 0,
        }

    if not uid or uid == "None":
        raise ValueError("position owner missing")

    settlement_key = (
        f"staking_reward:{position_id}:"
        f"{pool['calculated_at']}:{pool['accrued_total']}"
    )

    balance_after = economy_service.record_transaction(
        uid=uid,
        amount=pending,
        reason="staking:reward_settlement",
        meta={
            "idempotency_key": settlement_key,
            "position_id": position_id,
            "accrued_total": pool["accrued_total"],
            "reward_snapshot": pool["calculated_at"],
        },
    )

    def finalize(db):
        current = db.setdefault("reward_pools", {}).get(position_id)
        if not current:
            raise KeyError("reward pool missing")

        current_accrued = round(float(current.get("accrued_total", 0) or 0), 6)
        snapshot_accrued = round(float(pool.get("accrued_total", 0) or 0), 6)
        settled_total = round(float(current.get("settled_total", 0) or 0), 6)
        settled_total = max(settled_total, snapshot_accrued)
        current["settled_total"] = settled_total
        current["reward"] = max(0, round(current_accrued - settled_total, 6))
        current["status"] = "pending" if current["reward"] > 0 else "settled"
        current["settled_at"] = time.time()
        current["last_settlement_key"] = settlement_key
        return {
            "status": "settled" if current["reward"] == 0 else "settled_partial",
            "position_id": position_id,
            "amount": pending,
            "balance": balance_after,
        }

    return state_manager.atomic_update(finalize)
