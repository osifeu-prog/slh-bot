"""BNB deposit settlement authority.

Ownership is established by core.wallet_binding; on-chain facts come from
core.deposit_monitor; credit mutation goes through core.economy_service.
This module does not broadcast transactions or expose private keys.
"""

import state_manager

from core.deposit_monitor import verify_bnb_deposit
from core.wallet_binding import get_binding
from core.economy_service import record_transaction

CREDITS_PER_BNB = 1000


def settle_bnb_deposit(uid, tx_hash):
    uid = str(uid)
    if not isinstance(tx_hash, str) or not tx_hash.strip():
        raise ValueError("INVALID_TX_HASH")
    tx_hash = tx_hash.strip()

    binding = get_binding(uid)
    if not binding:
        raise ValueError("BNB_WALLET_NOT_VERIFIED")

    verified = verify_bnb_deposit(tx_hash)
    if not verified.get("ok"):
        raise ValueError(verified.get("error", "BNB_TX_NOT_VERIFIED"))

    sender = str(verified.get("from", ""))
    bound = str(binding.get("address", ""))
    if not sender or sender.lower() != bound.lower():
        raise ValueError("BNB_TX_SENDER_NOT_BOUND_WALLET")

    amount_bnb = float(verified.get("amount_bnb", 0))
    if amount_bnb <= 0:
        raise ValueError("INVALID_BNB_AMOUNT")

    credits = amount_bnb * CREDITS_PER_BNB
    idempotency_key = f"bnb:deposit:{tx_hash.lower()}"

    before_db = state_manager.load_db()
    already_recorded = any(
        entry.get("meta", {}).get("idempotency_key") == idempotency_key
        for entry in before_db.get("ledger", [])
    )

    balance_after = record_transaction(
        uid,
        credits,
        reason="bnb:deposit",
        meta={
            "idempotency_key": idempotency_key,
            "tx_hash": tx_hash,
            "bnb_amount": amount_bnb,
            "from": sender,
            "to": verified.get("to"),
            "block": verified.get("block"),
            "confirmations": verified.get("confirmations"),
        },
    )

    return {
        "ok": True,
        "uid": uid,
        "tx_hash": tx_hash,
        "amount_bnb": amount_bnb,
        "credits": credits,
        "balance_after": balance_after,
        "idempotent": already_recorded,
        "binding": bound,
    }
