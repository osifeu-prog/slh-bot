"""BNB deposit settlement authority.

Ownership is established by core.wallet_binding; on-chain facts come from
core.deposit_monitor; credit mutation goes through core.economy_service.
This module does not broadcast transactions or expose private keys.
"""

import os
from decimal import Decimal

from core.bnb_gate import bnb_deposits_open, bnb_readiness
from core.deposit_monitor import verify_bnb_deposit
from core.wallet_binding import get_binding
from core.economy_service import record_transaction

CREDITS_PER_BNB = 1000


def settle_bnb_deposit(uid, tx_hash):
    uid = str(uid)
    canary_uid = os.getenv("BNB_DEPOSITS_CANARY_UID", "").strip()
    canary_allowed = bool(canary_uid) and uid == canary_uid and bool(bnb_readiness().get("ready"))
    if not (bnb_deposits_open() or canary_allowed):
        raise ValueError("BNB_DEPOSITS_CLOSED")
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

    amount_wei = int(verified.get("amount_wei", 0) or 0)
    if amount_wei <= 0:
        raise ValueError("INVALID_BNB_AMOUNT")

    # 1 BNB = 10**18 wei and 1 BNB = 1000 Credits.
    # Keep the conversion exact in Decimal until the existing Credits ledger
    # boundary, which currently accepts numeric (float/int) balances.
    credits_exact = (
        Decimal(amount_wei) * Decimal(CREDITS_PER_BNB) / Decimal(10**18)
    )
    credits = float(credits_exact)
    amount_bnb = float(verified.get("amount_bnb", 0))
    idempotency_key = f"bnb:deposit:{tx_hash.lower()}"

    settlement = record_transaction(
        uid,
        credits,
        reason="bnb:deposit",
        meta={
            "idempotency_key": idempotency_key,
            "tx_hash": tx_hash,
            "bnb_amount": amount_bnb,
            "bnb_amount_wei": amount_wei,
            "from": sender,
            "to": verified.get("to"),
            "block": verified.get("block"),
            "confirmations": verified.get("confirmations"),
        },
        return_details=True,
    )
    settlement_status = str(settlement.get("status", "")).upper()
    if settlement_status == "CONFLICT":
        raise ValueError("BNB_DEPOSIT_IDEMPOTENCY_CONFLICT")
    if settlement_status not in {"APPLIED", "DUPLICATE"}:
        raise ValueError("BNB_DEPOSIT_RECORD_FAILED")

    return {
        "ok": True,
        "uid": uid,
        "tx_hash": tx_hash,
        "amount_bnb": amount_bnb,
        "amount_wei": amount_wei,
        "credits": credits if settlement_status == "APPLIED" else 0.0,
        "balance_after": settlement.get("balance_after"),
        "idempotent": settlement_status == "DUPLICATE",
        "settlement_status": settlement_status,
        "binding": bound,
    }
