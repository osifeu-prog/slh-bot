"""Atomic on-chain deposit claim authority.

All claim state and wallet mutations happen inside one state_manager.atomic_update
transaction. Handlers must never write claim state after a money mutation.
"""
from datetime import datetime, timezone
import state_manager


def record_bnb_deposit(uid, credits, amount_bnb, tx_hash, meta=None):
    uid = str(uid)
    meta = dict(meta or {})

    if not isinstance(credits, (int, float)) or credits <= 0:
        raise ValueError("INVALID_BNB_CREDITS")
    if not isinstance(amount_bnb, (int, float)) or amount_bnb <= 0:
        raise ValueError("INVALID_BNB_AMOUNT")
    if not isinstance(tx_hash, str) or not tx_hash.strip():
        raise ValueError("INVALID_TX_HASH")

    tx_hash = tx_hash.strip()

    def mutate(db):
        users = db.setdefault("users", {})
        if uid not in users:
            raise Exception("USER_NOT_FOUND")

        claimed = db.setdefault("claimed_deposits", {})
        existing = claimed.get(tx_hash)
        if existing is not None:
            return {
                "status": "duplicate",
                "uid": existing.get("uid", uid),
                "credits": existing.get("credits", 0),
                "balance": users[uid].get("wallet", {}).get("credits", 0),
                "tx_hash": tx_hash,
            }

        user = users[uid]
        wallet = user.setdefault("wallet", {})
        before = wallet.get("credits", 0)
        after = before + credits
        wallet["credits"] = after

        now = datetime.now(timezone.utc).isoformat()

        claimed[tx_hash] = {
            "uid": uid,
            "amount_bnb": amount_bnb,
            "credits": credits,
            "claimed_at": now,
        }

        db.setdefault("transactions", []).append({
            "uid": uid,
            "credits": credits,
            "type": "bnb",
            "amount_bnb": amount_bnb,
            "tx_hash": tx_hash,
            "timestamp": now,
        })

        ledger_meta = {**meta, "tx_hash": tx_hash, "amount_bnb": amount_bnb}
        db.setdefault("ledger", []).append({
            "time": now,
            "uid": uid,
            "before": before,
            "amount": credits,
            "after": after,
            "reason": "claim:bnb_deposit",
            "meta": ledger_meta,
        })

        return {
            "status": "applied",
            "uid": uid,
            "credits": credits,
            "balance": after,
            "tx_hash": tx_hash,
        }

    return state_manager.atomic_update(mutate)
