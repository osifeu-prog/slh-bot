"""Canonical, read-only asset truth helpers for SLH.

The wallet model distinguishes historical/internal token balance from live,
settled token balance. This module never mutates state and never creates,
burns, mints, or redistributes assets.
"""

from __future__ import annotations

from typing import Any


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def build_slH_asset_truth(wallet: dict[str, Any] | None) -> dict[str, Any]:
    """Return a deterministic read-only SLH asset truth view.

    token_balance is the current internal total represented by the wallet.
    live_token_balance is the subset proven through the live settlement path.
    exchange_reserved_slh is reserved inventory and therefore not spendable.

    Missing live_token_balance is intentionally treated as zero. It is never
    backfilled here.
    """
    source = wallet if isinstance(wallet, dict) else {}

    current_total = _number(source.get("token_balance"))
    current_live = _number(source.get("live_token_balance"))
    current_reserved = _number(source.get("exchange_reserved_slh"))

    current_reserved = max(current_reserved, 0.0)
    legacy_internal = max(current_total - current_live, 0.0)
    spendable_live = max(current_live - current_reserved, 0.0)

    if current_live > 0:
        provenance_status = "live_backed"
    elif current_total > 0:
        provenance_status = "legacy_internal"
    else:
        provenance_status = "empty"

    return {
        "asset": "SLH",
        "current_total": current_total,
        "current_live": current_live,
        "current_reserved": current_reserved,
        "legacy_internal": legacy_internal,
        "spendable_live": spendable_live,
        "provenance_status": provenance_status,
        "model": "canonical_live_settlement",
    }
