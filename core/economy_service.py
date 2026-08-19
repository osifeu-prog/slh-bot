import json
from pathlib import Path
from datetime import datetime, timezone

import state_manager

DB_PATH = Path("state/db.json")
LEDGER_PATH = Path("state/ledger.json")


def get_balance_safe(uid):
    db = state_manager.load_db()
    uid = str(uid)

    user = db.get("users", {}).get(uid)
    if not user:
        raise Exception("USER_NOT_FOUND")

    return user.get("wallet", {}).get("credits", 0)


def stake(uid, amount, meta=None):
    """Atomically move credits -> staked."""
    uid = str(uid)

    if not isinstance(amount, (int, float)):
        raise TypeError("amount must be numeric")
    if amount <= 0:
        raise ValueError("STAKE_AMOUNT_INVALID")

    meta = meta or {}

    def mutate(db):
        users = db.setdefault("users", {})

        if uid not in users:
            raise Exception("USER_NOT_FOUND")

        wallet = users[uid].setdefault("wallet", {})
        credits = wallet.get("credits", 0)
        staked = wallet.get("staked", 0)

        if credits < amount:
            raise ValueError("INSUFFICIENT_CREDITS")

        wallet["credits"] = credits - amount
        wallet["staked"] = staked + amount

        return {
            "credits": wallet["credits"],
            "staked": wallet["staked"],
        }

    return state_manager.atomic_update(mutate)


def unstake(uid, amount, meta=None):
    """Atomically move staked -> credits."""
    uid = str(uid)

    if not isinstance(amount, (int, float)):
        raise TypeError("amount must be numeric")
    if amount <= 0:
        raise ValueError("UNSTAKE_AMOUNT_INVALID")

    meta = meta or {}

    def mutate(db):
        users = db.setdefault("users", {})

        if uid not in users:
            raise Exception("USER_NOT_FOUND")

        wallet = users[uid].setdefault("wallet", {})
        credits = wallet.get("credits", 0)
        staked = wallet.get("staked", 0)

        if staked < amount:
            raise ValueError("INSUFFICIENT_STAKED")

        wallet["staked"] = staked - amount
        wallet["credits"] = credits + amount

        return {
            "credits": wallet["credits"],
            "staked": wallet["staked"],
        }

    return state_manager.atomic_update(mutate)


def record_ton_deposit(uid, tx_hash, credits, ton_amount, meta=None):
    """
    SINGLE MONEY AUTHORITY for verified TON deposits.

    Atomic invariants:
      - tx_hash can be credited only once
      - credits mutation happens inside atomic_update
      - TON transaction audit record is created with the mutation
    """
    uid = str(uid)

    if not uid:
        raise ValueError("USER_ID_REQUIRED")

    if not tx_hash:
        raise ValueError("TX_HASH_REQUIRED")

    if not isinstance(credits, (int, float)) or credits <= 0:
        raise ValueError("TON_CREDITS_INVALID")

    if not isinstance(ton_amount, (int, float)) or ton_amount <= 0:
        raise ValueError("TON_AMOUNT_INVALID")

    meta = meta or {}

    def mutate(db):
        users = db.setdefault("users", {})

        if uid not in users:
            raise Exception("USER_NOT_FOUND")

        used_txs = db.setdefault("used_ton_txs", [])

        if tx_hash in used_txs:
            return None

        wallet = users[uid].setdefault("wallet", {})

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
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        return {
            "credits": after,
            "before": before,
            "amount": credits,
            "tx_hash": tx_hash,
        }

    result = state_manager.atomic_update(mutate)

    if result is not None:
        # Audit entry belongs to the Money Authority.
        ledger = []

        if LEDGER_PATH.exists():
            try:
                ledger = json.loads(
                    LEDGER_PATH.read_text(encoding="utf-8")
                )
            except Exception:
                ledger = []

        ledger.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": result["before"],
            "amount": result["amount"],
            "after": result["credits"],
            "reason": "ton:deposit",
            "meta": {
                **meta,
                "tx_hash": tx_hash,
                "ton_amount": ton_amount,
            }
        })

        LEDGER_PATH.write_text(
            json.dumps(
                ledger,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

    return result


def record_transaction(uid, amount, reason="unknown", meta=None):
    """
    SINGLE MONEY AUTHORITY.

    Every credit mutation:
        load -> validate -> mutate -> ledger -> atomic save

    No caller should modify wallet["credits"] directly.
    """
    uid = str(uid)

    if not isinstance(amount, (int, float)):
        raise TypeError("amount must be numeric")

    if not reason:
        raise ValueError("reason is required")

    meta = meta or {}

    def mutate(db):
        users = db.setdefault("users", {})

        if uid not in users:
            raise Exception("USER_NOT_FOUND")

        wallet = users[uid].setdefault("wallet", {})

        before = wallet.get("credits", 0)
        after = before + amount

        if after < 0:
            raise ValueError("INSUFFICIENT_CREDITS")

        wallet["credits"] = after

        ledger = []
        if LEDGER_PATH.exists():
            try:
                ledger = json.loads(
                    LEDGER_PATH.read_text(encoding="utf-8")
                )
            except Exception:
                ledger = []

        ledger.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": before,
            "amount": amount,
            "after": after,
            "reason": reason,
            "meta": meta
        })

        LEDGER_PATH.write_text(
            json.dumps(
                ledger,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        return after

    return state_manager.atomic_update(mutate)
