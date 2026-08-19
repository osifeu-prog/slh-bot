import json
from pathlib import Path
from datetime import datetime, timezone
import state_manager

DB_PATH = Path("state/db.json")




def get_balance_safe(uid):
    db = state_manager.load_db()
    uid = str(uid)

    user = db.get("users", {}).get(uid)

    if not user:
        raise Exception("USER_NOT_FOUND")

    return user.get("wallet", {}).get("credits", 0)


def record_transaction(uid, amount, reason="unknown", meta=None):
    uid = str(uid)

    if not isinstance(amount, (int, float)):
        raise TypeError("amount must be numeric")

    meta = meta or {}

    def mutate(db):
        users = db.setdefault("users", {})

        if uid not in users:
            raise Exception("USER_NOT_FOUND")

        user = users[uid]
        wallet = user.setdefault("wallet", {})

        before = wallet.get("credits", 0)
        after = before + amount

        if after < 0:
            raise ValueError("INSUFFICIENT_CREDITS")

        wallet["credits"] = after

        ledger = db.setdefault("ledger", [])

        ledger.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": before,
            "amount": amount,
            "after": after,
            "reason": reason,
            "meta": meta,
        })

        return after

    return state_manager.atomic_update(mutate)


def record_ton_deposit(
    uid,
    credits,
    ton_amount,
    tx_hash,
    meta=None,
):
    """
    Atomic TON deposit authority.

    Guarantees:
    1. transaction hash can only be credited once
    2. wallet credit mutation and transaction registration happen atomically
    3. ledger entry is created
    """

    uid = str(uid)
    meta = meta or {}

    # P0 input validation: TON deposits may only create positive credits.
    if not isinstance(credits, (int, float)):
        raise TypeError("credits must be numeric")

    if credits <= 0:
        raise ValueError("INVALID_TON_CREDITS")

    if not isinstance(ton_amount, (int, float)):
        raise TypeError("ton_amount must be numeric")

    if ton_amount <= 0:
        raise ValueError("INVALID_TON_AMOUNT")

    if not isinstance(tx_hash, str) or not tx_hash.strip():
        raise ValueError("INVALID_TX_HASH")

    tx_hash = tx_hash.strip()

    def mutate(db):
        users = db.setdefault("users", {})

        if uid not in users:
            raise Exception("USER_NOT_FOUND")

        used_txs = db.setdefault("used_ton_txs", [])

        if tx_hash in used_txs:
            return None

        user = users[uid]
        wallet = user.setdefault("wallet", {})

        before = wallet.get("credits", 0)
        after = before + credits

        wallet["credits"] = after

        used_txs.append(tx_hash)

        db.setdefault("transactions", []).append({
            "uid": uid,
            "credits": credits,
            "type": "ton",
            "ton_amount": ton_amount,
            "tx_hash": tx_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        ledger = db.setdefault("ledger", [])

        ledger.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": before,
            "amount": credits,
            "after": after,
            "reason": "ton:deposit",
            "meta": {
                **meta,
                "tx_hash": tx_hash,
                "ton_amount": ton_amount,
            },
        })

        return after

    return state_manager.atomic_update(mutate)
def stake_credits(uid, amount, meta=None):
    """
    Atomically move credits into staking.

    Money invariant:
        credits decreases by amount
        staked increases by amount

    Both mutations and the ledger entry are committed together.
    """
    if not isinstance(amount, (int, float)):
        raise TypeError("amount must be numeric")

    if amount <= 0:
        raise ValueError("amount must be positive")

    meta = meta or {}

    def mutate(db):
        users = db.setdefault("users", {})
        user = users.get(str(uid))

        if user is None:
            raise ValueError("user not found")

        wallet = user.setdefault("wallet", {})

        before_credits = wallet.get("credits", 0)
        before_staked = wallet.get("staked", 0)

        if before_credits < amount:
            raise ValueError("insufficient credits")

        after_credits = before_credits - amount
        after_staked = before_staked + amount

        wallet["credits"] = after_credits
        wallet["staked"] = after_staked

        db.setdefault("ledger", []).append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": str(uid),
            "before": before_credits,
            "amount": -amount,
            "after": after_credits,
            "reason": "staking:stake",
            "meta": {
                **meta,
                "staked_before": before_staked,
                "staked_after": after_staked,
            },
        })

        return {
            "credits": after_credits,
            "staked": after_staked,
        }

    return state_manager.atomic_update(mutate)


def unstake_credits(uid, amount, meta=None):
    """
    Atomically return staked credits to the available balance.

    Money invariant:
        staked decreases by amount
        credits increases by amount

    Both mutations and the ledger entry are committed together.
    """
    if not isinstance(amount, (int, float)):
        raise TypeError("amount must be numeric")

    if amount <= 0:
        raise ValueError("amount must be positive")

    meta = meta or {}

    def mutate(db):
        users = db.setdefault("users", {})
        user = users.get(str(uid))

        if user is None:
            raise ValueError("user not found")

        wallet = user.setdefault("wallet", {})

        before_credits = wallet.get("credits", 0)
        before_staked = wallet.get("staked", 0)

        if before_staked < amount:
            raise ValueError("insufficient staked balance")

        after_staked = before_staked - amount
        after_credits = before_credits + amount

        wallet["staked"] = after_staked
        wallet["credits"] = after_credits

        db.setdefault("ledger", []).append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": str(uid),
            "before": before_credits,
            "amount": amount,
            "after": after_credits,
            "reason": "staking:unstake",
            "meta": {
                **meta,
                "staked_before": before_staked,
                "staked_after": after_staked,
            },
        })

        return {
            "credits": after_credits,
            "staked": after_staked,
        }

    return state_manager.atomic_update(mutate)
