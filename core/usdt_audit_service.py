"""Read-only USDT-on-TON audit service.

This module never credits balances and never broadcasts transactions.
It uses TON Center's indexed v3 Jetton transfer API to inspect the
allow-listed Tether USDT master contract on mainnet.
"""
from __future__ import annotations

import os
from decimal import Decimal

import requests

from core.ton_wallet_binding import get_ton_binding, normalize_ton_address


TONCENTER_V3_URL = os.getenv(
    "TONCENTER_V3_URL",
    "https://toncenter.com/api/v3",
).rstrip("/")

USDT_MASTER = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
USDT_DECIMALS = 6


def _headers():
    key = (os.getenv("TONCENTER_API_KEY") or "").strip()
    return {"X-API-Key": key} if key else {}


def _settings():
    import state_manager
    db = state_manager.load_db()
    settings = db.get("ton_settings", {}) or {}
    treasury = os.getenv("TON_WALLET", "").strip() or settings.get("wallet")
    return treasury


def list_inbound_usdt(uid, limit=20):
    """Return recent inbound USDT transfers into the configured TON treasury."""
    binding = get_ton_binding(str(uid))
    if not binding:
        raise ValueError("TON_WALLET_NOT_VERIFIED")

    treasury = _settings()
    if not treasury:
        raise ValueError("TON_NOT_CONFIGURED")

    response = requests.get(
        f"{TONCENTER_V3_URL}/jetton/transfers",
        params={
            "owner_address": treasury,
            "jetton_master": USDT_MASTER,
            "direction": "in",
            "limit": max(1, min(int(limit), 100)),
            "sort": "desc",
        },
        headers=_headers(),
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    if not isinstance(data, dict):
        raise ValueError("TONCENTER_INVALID_RESPONSE")

    transfers = data.get("jetton_transfers") or []
    result = []

    bound = normalize_ton_address(binding.get("address_raw") or binding.get("address"))
    treasury_raw = normalize_ton_address(treasury)

    for row in transfers:
        if not isinstance(row, dict):
            continue

        source = str(row.get("source") or "").strip()
        destination = str(row.get("destination") or "").strip()
        try:
            raw_amount = Decimal(str(row.get("amount") or "0"))
            amount = raw_amount / (Decimal(10) ** USDT_DECIMALS)
        except Exception:
            amount = Decimal("0")

        result.append({
            "transaction_hash": str(row.get("transaction_hash") or ""),
            "transaction_lt": str(row.get("transaction_lt") or ""),
            "source": source,
            "destination": destination,
            "amount_usdt": float(amount),
            "jetton_master": str(row.get("jetton_master") or ""),
            "source_bound_wallet": (
                bool(source)
                and normalize_ton_address(source) == bound
            ),
            "destination_treasury": (
                bool(destination)
                and normalize_ton_address(destination) == treasury_raw
            ),
            "transaction_aborted": bool(row.get("transaction_aborted")),
            "forward_payload": row.get("forward_payload"),
            "decoded_forward_payload": row.get("decoded_forward_payload"),
            "custom_payload": row.get("custom_payload"),
        })

    return {
        "ok": True,
        "asset": "USDT",
        "network": "-239",
        "jetton_master": USDT_MASTER,
        "decimals": USDT_DECIMALS,
        "treasury": treasury,
        "bound_wallet": binding.get("address"),
        "transfers": result,
    }


def audit_usdt_tx(uid, tx_hash):
    tx_hash = str(tx_hash or "").strip()
    if not tx_hash:
        raise ValueError("INVALID_TX_HASH")

    data = list_inbound_usdt(uid, limit=100)
    for row in data["transfers"]:
        if row["transaction_hash"].lower() == tx_hash.lower():
            return {
                "ok": True,
                "match": True,
                "settlement": "NOT_PERFORMED",
                "transfer": row,
                "asset": "USDT",
                "jetton_master": data["jetton_master"],
                "treasury": data["treasury"],
                "bound_wallet": data["bound_wallet"],
            }

    return {
        "ok": True,
        "match": False,
        "settlement": "NOT_PERFORMED",
        "asset": "USDT",
        "jetton_master": data["jetton_master"],
        "treasury": data["treasury"],
        "bound_wallet": data["bound_wallet"],
    }
