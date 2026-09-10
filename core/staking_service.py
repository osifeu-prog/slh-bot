"""Atomic staking workflow authority.

All wallet + stake-position mutations are performed in one atomic DB update.
This module is the staking-specific mutation boundary; callers must not mutate
wallet or stake_positions directly.
"""

import time
from datetime import datetime, timezone

import state_manager


def stake_locked(uid, amount, lock_days=30, meta=None):
    uid = str(uid)
    amount = float(amount)
    lock_days = int(lock_days)
    meta = dict(meta or {})

    if amount <= 0:
        raise ValueError("amount must be positive")
    if lock_days <= 0:
        raise ValueError("lock_days must be positive")

    def mutate(db):
        users = db.setdefault("users", {})
        user = users.get(uid)
        if user is None:
            raise ValueError("user not found")

        wallet = user.setdefault("wallet", {})
        credits = float(wallet.get("credits", 0) or 0)
        staked = float(wallet.get("staked", 0) or 0)
        if credits < amount:
            raise ValueError("insufficient credits")

        positions = db.setdefault("stake_positions", {})
        now = time.time()
        position_id = f"sp_{int(now * 1000)}"
        while position_id in positions:
            now += 0.001
            position_id = f"sp_{int(now * 1000)}"

        wallet["credits"] = credits - amount
        wallet["staked"] = staked + amount
        positions[position_id] = {
            "id": position_id,
            "uid": uid,
            "amount": amount,
            "lock_days": lock_days,
            "created_at": now,
            "unlocks_at": now + lock_days * 86400,
            "status": "locked",
        }

        db.setdefault("ledger", []).append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": credits,
            "amount": -amount,
            "after": credits - amount,
            "reason": "staking:stake_locked",
            "meta": {
                **meta,
                "position_id": position_id,
                "lock_days": lock_days,
                "staked_before": staked,
                "staked_after": staked + amount,
            },
        })

        return {
            "position": positions[position_id],
            "credits": credits - amount,
            "staked": staked + amount,
        }

    return state_manager.atomic_update(mutate)


def unstake_locked(uid, position_id, meta=None):
    uid = str(uid)
    position_id = str(position_id)
    meta = dict(meta or {})

    def mutate(db):
        users = db.setdefault("users", {})
        user = users.get(uid)
        if user is None:
            raise ValueError("user not found")

        position = db.setdefault("stake_positions", {}).get(position_id)
        if not position or str(position.get("uid")) != uid:
            raise ValueError("position not found")
        if position.get("status") == "unlocked":
            return {"status": "duplicate", "position_id": position_id}
        if time.time() < float(position.get("unlocks_at", 0)):
            raise ValueError("still locked")

        amount = float(position.get("amount", 0) or 0)
        if amount <= 0:
            raise ValueError("invalid position amount")

        wallet = user.setdefault("wallet", {})
        credits = float(wallet.get("credits", 0) or 0)
        staked = float(wallet.get("staked", 0) or 0)
        if staked < amount:
            raise ValueError("insufficient staked balance")

        wallet["staked"] = staked - amount
        wallet["credits"] = credits + amount
        position["status"] = "unlocked"
        position["unlocked_at"] = time.time()

        db.setdefault("ledger", []).append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": credits,
            "amount": amount,
            "after": credits + amount,
            "reason": "staking:unstake_locked",
            "meta": {
                **meta,
                "position_id": position_id,
                "staked_before": staked,
                "staked_after": staked - amount,
            },
        })

        return {
            "status": "unlocked",
            "position": position,
            "credits": credits + amount,
            "staked": staked - amount,
        }

    return state_manager.atomic_update(mutate)
