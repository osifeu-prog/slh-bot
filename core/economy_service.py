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


def record_transaction(uid, amount, reason="unknown", meta=None, return_status=False):
    uid = str(uid)

    if not isinstance(amount, (int, float)):
        raise TypeError("amount must be numeric")

    meta = meta or {}

    def mutate(db):
        users = db.setdefault("users", {})

        if uid not in users:
            raise Exception("USER_NOT_FOUND")

        ledger = db.setdefault("ledger", [])

        idempotency_key = meta.get("idempotency_key")
        if idempotency_key:
            for entry in ledger:
                if entry.get("meta", {}).get("idempotency_key") == idempotency_key:
                    if return_status:
                        return {"after": entry["after"], "idempotent": True}
                    return entry["after"]

        user = users[uid]
        wallet = user.setdefault("wallet", {})

        before = wallet.get("credits", 0)
        after = before + amount

        if after < 0:
            raise ValueError("INSUFFICIENT_CREDITS")

        wallet["credits"] = after

        ledger.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": before,
            "amount": amount,
            "after": after,
            "reason": reason,
            "meta": meta,
        })

        if return_status:
            return {"after": after, "idempotent": False}
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
    """
    uid = str(uid)
    if not uid:
        raise ValueError("INVALID_UID")
    if not isinstance(credits, (int, float)) or credits <= 0:
        raise ValueError("INVALID_CREDITS")
    if not isinstance(ton_amount, (int, float)) or ton_amount <= 0:
        raise ValueError("INVALID_TON_AMOUNT")
    if not isinstance(tx_hash, str) or not tx_hash.strip():
        raise ValueError("INVALID_TX_HASH")

    meta = dict(meta or {})
    meta["tx_hash"] = tx_hash.strip()
    meta["ton_amount"] = ton_amount

    def mutate(db):
        users = db.setdefault("users", {})
        user = users.get(uid)
        if not user:
            raise ValueError("USER_NOT_FOUND")

        used = db.setdefault("used_ton_txs", {})
        tx_key = tx_hash.strip().lower()
        if tx_key in used:
            existing = used[tx_key]
            return {
                "ok": True,
                "idempotent": True,
                "uid": uid,
                "tx_hash": tx_hash.strip(),
                "credits": existing.get("credits", credits),
                "balance_after": existing.get("balance_after", user.get("wallet", {}).get("credits", 0)),
            }

        wallet = user.setdefault("wallet", {})
        before = wallet.get("credits", 0)
        after = before + credits
        wallet["credits"] = after

        ledger = db.setdefault("ledger", [])
        ledger.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": before,
            "amount": credits,
            "after": after,
            "reason": "ton:deposit",
            "meta": meta,
        })

        used[tx_key] = {
            "uid": uid,
            "credits": credits,
            "ton_amount": ton_amount,
            "balance_after": after,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

        return {
            "ok": True,
            "idempotent": False,
            "uid": uid,
            "tx_hash": tx_hash.strip(),
            "credits": credits,
            "balance_after": after,
        }

    return state_manager.atomic_update(mutate)
