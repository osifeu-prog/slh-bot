"""Read-only TON native wallet and Jetton asset model.

This module never signs, broadcasts, credits internal balances, or stores keys.
Jetton deposits must use a separate allowlist + on-chain relationship validation
before any financial settlement is enabled.
"""

from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import requests

from core.ton_wallet_binding import get_ton_binding, normalize_ton_address

TONAPI_URL = os.getenv("TONAPI_URL", "https://tonapi.io").rstrip("/")
TONAPI_TOKEN = os.getenv("TONAPI_TOKEN", "").strip()


class TONJettonReadError(ValueError):
    pass


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TONAPI_TOKEN}"} if TONAPI_TOKEN else {}


def _bound_address(uid: str) -> str:
    binding = get_ton_binding(str(uid))
    if not binding:
        raise TONJettonReadError("TON_WALLET_NOT_VERIFIED")
    return normalize_ton_address(binding.get("address_raw") or binding.get("address"))


def _decimal_balance(raw: str, decimals: int) -> str:
    try:
        value = Decimal(str(raw))
    except InvalidOperation as exc:
        raise TONJettonReadError("TON_JETTON_BALANCE_INVALID") from exc
    if not value.is_finite() or value < 0:
        raise TONJettonReadError("TON_JETTON_BALANCE_INVALID")
    return str(value / (Decimal(10) ** decimals))


def list_jetton_balances(uid: str, *, limit: int = 100) -> dict:
    """Return indexed Jetton balances for the user's verified TON wallet."""
    if limit < 1 or limit > 1000:
        raise TONJettonReadError("INVALID_JETTON_LIMIT")

    address = _bound_address(str(uid))
    url = f"{TONAPI_URL}/v2/accounts/{quote(address, safe='')}/jettons"

    try:
        response = requests.get(
            url,
            headers=_headers(),
            params={"limit": limit},
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise TONJettonReadError("TONAPI_UNAVAILABLE") from exc
    except ValueError as exc:
        raise TONJettonReadError("TONAPI_INVALID_RESPONSE") from exc

    if not isinstance(payload, dict):
        raise TONJettonReadError("TONAPI_INVALID_RESPONSE")

    raw_balances = payload.get("balances")
    if raw_balances is None:
        raw_balances = []

    if not isinstance(raw_balances, list):
        raise TONJettonReadError("TONAPI_INVALID_RESPONSE")

    balances = []
    for item in raw_balances:
        if not isinstance(item, dict):
            continue
        jetton = item.get("jetton") or {}
        if not isinstance(jetton, dict):
            jetton = {}

        try:
            decimals = int(jetton.get("decimals") or 0)
        except (TypeError, ValueError):
            decimals = 0
        if decimals < 0 or decimals > 36:
            decimals = 0

        raw_balance = str(item.get("balance") or "0")
        balances.append(
            {
                "jetton_master": str(
                    jetton.get("address")
                    or jetton.get("master")
                    or jetton.get("jetton_address")
                    or ""
                ),
                "name": str(jetton.get("name") or ""),
                "symbol": str(jetton.get("symbol") or ""),
                "decimals": decimals,
                "balance_raw": raw_balance,
                "balance": _decimal_balance(raw_balance, decimals),
                "verification": str(jetton.get("verification") or "unknown"),
                "image": jetton.get("image") or jetton.get("preview") or None,
            }
        )

    return {
        "ok": True,
        "chain": "ton",
        "network": "mainnet",
        "address": address,
        "balances": balances,
        "read_only": True,
        "source": "tonapi",
    }


def trusted_jetton_master_configured() -> bool:
    return bool(os.getenv("SLH_TON_JETTON_MASTER", "").strip())


def trusted_jetton_master() -> str | None:
    value = os.getenv("SLH_TON_JETTON_MASTER", "").strip()
    if not value:
        return None
    return normalize_ton_address(value)
