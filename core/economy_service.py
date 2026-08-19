import json
from pathlib import Path
from datetime import datetime, timezone
import state_manager

DB_PATH = Path("state/db.json")
LEDGER_PATH = Path("state/ledger.json")


def _load_ledger():
    if not LEDGER_PATH.exists():
        return []
    return json.loads(
        LEDGER_PATH.read_text(encoding="utf-8")
    )


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

        ledger = _load_ledger()

        ledger.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": before,
            "amount": amount,
            "after": after,
            "reason": reason,
            "meta": meta,
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

        ledger = _load_ledger()

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
