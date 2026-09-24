"""Canonical TON deposit settlement authority.

Ownership comes from core.ton_wallet_binding. This service verifies an observed
TON transaction to the configured treasury, optionally requires the personal
SLH<uid> comment, and mutates Credits only through economy_service.record_ton_deposit.
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Iterable

import requests

import state_manager
from core.economy_service import record_ton_deposit
from core.ton_wallet_binding import get_ton_binding, normalize_ton_address


TONCENTER_URL = os.getenv("TONCENTER_URL", "https://toncenter.com/api/v2").rstrip("/")
TONCENTER_API_KEY = os.getenv("TONCENTER_API_KEY", "").strip()
TON_RATE_MIN = Decimal("100")
TON_RATE_MAX = Decimal("110")
NANO = Decimal(10) ** 9


def _deposits_open() -> bool:
    return os.getenv("TON_DEPOSITS_OPEN", "0").strip() == "1"


def _settings():
    settings = state_manager.load_db().get("ton_settings", {}) or {}
    wallet = os.getenv("TON_WALLET", "").strip() or settings.get("wallet")
    rate = os.getenv("TON_CREDITS_PER_TON", "").strip() or settings.get("credits_per_ton")
    if rate in (None, "", 0):
        rate = settings.get("rate")
    return wallet, Decimal(str(rate or 0))


def deposits_are_open() -> bool:
    if not _deposits_open():
        return False
    treasury, rate = _settings()
    return bool(treasury and TON_RATE_MIN <= rate <= TON_RATE_MAX)


def memo_for(uid) -> str:
    return f"SLH{uid}"


def _headers():
    return {"X-API-Key": TONCENTER_API_KEY} if TONCENTER_API_KEY else {}


def _address_value(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return (
            value.get("address")
            or value.get("source")
            or value.get("destination")
            or ""
        )
    return ""


def _find_ton_transaction(treasury: str, tx_hash: str):
    response = requests.get(
        f"{TONCENTER_URL}/getTransactions",
        params={"address": treasury, "limit": 100, "archival": "true"},
        headers=_headers(),
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok", True):
        raise ValueError("TONCENTER_ERROR")

    for tx in data.get("result", []) or []:
        transaction_id = tx.get("transaction_id") or {}
        candidate_hash = str(transaction_id.get("hash") or "")
        if candidate_hash.lower() != tx_hash.lower():
            continue

        in_msg = tx.get("in_msg") or {}
        value = int(in_msg.get("value") or 0)
        source = _address_value(in_msg.get("source"))
        destination = _address_value(in_msg.get("destination")) or _address_value(in_msg.get("dest"))
        memo = str(in_msg.get("message") or "").strip()

        return {
            "tx_hash": candidate_hash,
            "from": source,
            "to": destination,
            "amount_ton": Decimal(value) / NANO,
            "memo": memo,
            "observed": True,
            "utime": tx.get("utime"),
            "lt": transaction_id.get("lt"),
        }

    raise ValueError("TON_TX_NOT_FOUND")


def _settle_observed_transaction(uid, transaction, treasury, rate, binding):
    bound_raw = normalize_ton_address(binding.get("address_raw") or binding.get("address"))
    sender = transaction.get("from") or ""
    if not sender:
        raise ValueError("TON_TX_SENDER_MISSING")
    if normalize_ton_address(sender) != bound_raw:
        raise ValueError("TON_TX_SENDER_NOT_BOUND_WALLET")

    destination = transaction.get("to") or ""
    if not destination:
        raise ValueError("TON_TX_RECIPIENT_MISSING")
    if normalize_ton_address(destination) != normalize_ton_address(treasury):
        raise ValueError("TON_TX_RECIPIENT_NOT_TREASURY")

    amount_ton = Decimal(str(transaction.get("amount_ton") or 0))
    if amount_ton <= 0:
        raise ValueError("INVALID_TON_AMOUNT")

    if str(transaction.get("memo") or "").strip().lower() != memo_for(uid).lower():
        raise ValueError("TON_TX_MEMO_MISMATCH")

    credits = (amount_ton * rate).quantize(Decimal("0.01"))
    if credits <= 0:
        raise ValueError("INVALID_TON_CREDITS")

    tx_hash = str(transaction.get("tx_hash") or "").strip()
    if not tx_hash:
        raise ValueError("INVALID_TX_HASH")

    result = record_ton_deposit(
        uid=uid,
        credits=float(credits),
        ton_amount=float(amount_ton),
        tx_hash=tx_hash,
        meta={
            "idempotency_key": f"TON-DEPOSIT-{tx_hash.lower()}",
            "source": "ton_verified_binding_v1",
            "binding_address": binding.get("address"),
            "binding_address_raw": bound_raw,
            "treasury": treasury,
            "memo": memo_for(uid),
            "rate": str(rate),
            "utime": transaction.get("utime"),
            "lt": transaction.get("lt"),
        },
    )

    idempotent = result is None
    return {
        "ok": True,
        "uid": uid,
        "tx_hash": tx_hash,
        "amount_ton": float(amount_ton),
        "credits": 0.0 if idempotent else float(credits),
        "idempotent": idempotent,
        "binding": binding.get("address"),
        "treasury": treasury,
        "rate": float(rate),
    }


def settle_ton_deposit(uid, tx_hash):
    uid = str(uid)
    if not deposits_are_open():
        raise ValueError("TON_DEPOSITS_CLOSED")
    if not isinstance(tx_hash, str) or not tx_hash.strip():
        raise ValueError("INVALID_TX_HASH")
    tx_hash = tx_hash.strip()

    binding = get_ton_binding(uid)
    if not binding:
        raise ValueError("TON_WALLET_NOT_VERIFIED")

    treasury, rate = _settings()
    if not treasury or rate <= 0:
        raise ValueError("TON_NOT_CONFIGURED")
    if _deposits_open() and not (TON_RATE_MIN <= rate <= TON_RATE_MAX):
        raise ValueError("TON_RATE_NOT_SAFE")

    transaction = _find_ton_transaction(treasury, tx_hash)
    return _settle_observed_transaction(uid, transaction, treasury, rate, binding)

def credit_new_ton_deposits(uid):
    """Scan recent treasury inbound transactions and credit matching bound deposits."""
    uid = str(uid)
    if not _deposits_open():
        raise ValueError("TON_DEPOSITS_CLOSED")

    binding = get_ton_binding(uid)
    if not binding:
        raise ValueError("TON_WALLET_NOT_VERIFIED")

    treasury, rate = _settings()
    if not treasury or rate <= 0:
        raise ValueError("TON_NOT_CONFIGURED")

    response = requests.get(
        f"{TONCENTER_URL}/getTransactions",
        params={"address": treasury, "limit": 100, "archival": "true"},
        headers=_headers(),
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok", True):
        raise ValueError("TONCENTER_ERROR")

    target = normalize_ton_address(treasury)
    bound = normalize_ton_address(binding.get("address_raw") or binding.get("address"))
    expected_memo = memo_for(uid).lower()
    credited = []

    for tx in data.get("result", []) or []:
        transaction_id = tx.get("transaction_id") or {}
        tx_hash = str(transaction_id.get("hash") or "").strip()
        if not tx_hash:
            continue
        in_msg = tx.get("in_msg") or {}
        transaction = {
            "tx_hash": tx_hash,
            "from": _address_value(in_msg.get("source")),
            "to": _address_value(in_msg.get("destination")) or _address_value(in_msg.get("dest")),
            "amount_ton": Decimal(int(in_msg.get("value") or 0)) / NANO,
            "memo": str(in_msg.get("message") or "").strip(),
            "observed": True,
            "utime": tx.get("utime"),
            "lt": transaction_id.get("lt"),
        }

        try:
            if not transaction["from"] or normalize_ton_address(transaction["from"]) != bound:
                continue
            if not transaction["to"] or normalize_ton_address(transaction["to"]) != target:
                continue
            if transaction["memo"].lower() != expected_memo:
                continue
            result = _settle_observed_transaction(uid, transaction, treasury, rate, binding)
        except ValueError as exc:
            if str(exc) in {
                "TON_TX_SENDER_NOT_BOUND_WALLET",
                "TON_TX_RECIPIENT_NOT_TREASURY",
                "TON_TX_MEMO_MISMATCH",
                "INVALID_TON_AMOUNT",
                "TON_TX_SENDER_MISSING",
                "TON_TX_RECIPIENT_MISSING",
            }:
                continue
            raise

        if not result["idempotent"]:
            credited.append(result)

    return credited
