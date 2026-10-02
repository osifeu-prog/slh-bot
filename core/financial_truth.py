"""Canonical read-only unified financial truth for SLH OS.

This module composes the existing financial authorities into one presentation
model for the Mini App / Control Plane. It never mutates balances, ledgers,
bindings, or settlement gates.

Authoritative sources:
- state/db.json for internal user wallet and bindings
- core.asset_truth for SLH live/legacy semantics
- core.bnb_gate for BNB settlement readiness
- core.stars_financial_truth for Telegram Stars reconciliation
- TON gate settings already used by core.ton_deposit_service

No external chain balance is inferred here. On-chain settlement is represented
by the existing, internally proven live balance and explicit gate/binding state.
"""

from __future__ import annotations

import os
from typing import Any, Callable

import state_manager

from core.asset_truth import build_slH_asset_truth
from core.bnb_gate import bnb_readiness
from core.stars_financial_truth import build_stars_financial_truth


TON_RATE_MIN = 100.0
TON_RATE_MAX = 110.0


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _ton_settings(db: dict) -> tuple[str, float, bool]:
    settings = db.get("ton_settings", {})
    settings = settings if isinstance(settings, dict) else {}

    treasury = os.getenv("TON_WALLET", "").strip() or str(
        settings.get("wallet") or ""
    ).strip()

    rate_raw = (
        os.getenv("TON_CREDITS_PER_TON", "").strip()
        or settings.get("credits_per_ton")
        or settings.get("rate")
        or 0
    )
    try:
        rate = float(rate_raw or 0)
    except (TypeError, ValueError):
        rate = 0.0

    flag_open = os.getenv("TON_DEPOSITS_OPEN", "0").strip() == "1"
    effective_open = bool(
        flag_open
        and treasury
        and TON_RATE_MIN <= rate <= TON_RATE_MAX
    )
    return treasury, rate, effective_open


def _binding_for_uid(rows: Any, uid: str, *, chain: str | None = None) -> dict | None:
    if not isinstance(rows, dict):
        return None
    for row in rows.values():
        if not isinstance(row, dict):
            continue
        if str(row.get("uid")) != uid:
            continue
        if chain is not None and str(row.get("chain")) != chain:
            continue
        return row
    return None


def _internal_truth(user: dict) -> dict:
    wallet = user.get("wallet", {})
    wallet = wallet if isinstance(wallet, dict) else {}
    return {
        "credits_available": _number(wallet.get("credits")),
        "credits_staked": _number(wallet.get("staked")),
        "slh": build_slH_asset_truth(wallet),
    }


def build_financial_truth(
    uid: str,
    *,
    owner: bool = False,
    stars_builder: Callable[..., dict] = build_stars_financial_truth,
) -> dict:
    """Build one deterministic, read-only financial truth view."""
    uid = str(uid)
    db = state_manager.load_db()
    users = db.get("users", {}) if isinstance(db, dict) else {}
    user = users.get(uid) if isinstance(users, dict) else None
    if not isinstance(user, dict):
        raise ValueError("USER_NOT_FOUND")

    internal = _internal_truth(user)

    bnb_binding = _binding_for_uid(
        db.get("wallet_bindings", {}),
        uid,
        chain="bsc",
    )
    bnb = bnb_readiness()

    ton_binding = _binding_for_uid(db.get("ton_wallet_bindings", {}), uid)
    ton_treasury, ton_rate, ton_open = _ton_settings(db)

    stars = stars_builder(uid, owner=owner)

    blockers = []
    if not bnb.get("effective_open"):
        blockers.append("BNB_SETTLEMENT_CLOSED")
    if not ton_open:
        blockers.append("TON_SETTLEMENT_CLOSED")
    if internal["slh"]["current_live"] <= 0:
        blockers.append("NO_SLH_LIVE_BALANCE")

    stars_status = str(stars.get("status") or "")
    if owner and stars_status != "LIVE_RECONCILED":
        blockers.append("STARS_RECONCILIATION_NOT_LIVE")

    overall_status = "READ_ONLY_TRUTH"
    if owner and stars_status == "LIVE_RECONCILED":
        overall_status = "READ_ONLY_TRUTH_STARS_RECONCILED"

    return {
        "schema": "financial_truth.v1",
        "generated_at": stars.get("generated_at"),
        "scope": "owner" if owner else "personal",
        "status": overall_status,
        "read_only": True,
        "source_of_truth": "state/db.json",
        "user": {
            "uid": uid,
            "display_name": (
                user.get("display_name")
                or user.get("name")
                or f"User {uid}"
            ),
        },
        "internal": internal,
        "stars": stars,
        "rails": {
            "bnb": {
                "binding_status": "VERIFIED" if bnb_binding else "NOT_VERIFIED",
                "binding_address": (
                    bnb_binding.get("address") if bnb_binding else None
                ),
                "settlement_open": bool(bnb.get("effective_open")),
                "gate_ready": bool(bnb.get("ready")),
                "flag_open": bool(bnb.get("flag_open")),
                "chain_id": bnb.get("chain_id"),
                "confirmations_required": bnb.get("confirmations_required"),
                "reasons": list(bnb.get("reasons") or []),
            },
            "ton": {
                "binding_status": "VERIFIED" if ton_binding else "NOT_VERIFIED",
                "binding_address": (
                    ton_binding.get("address") if ton_binding else None
                ),
                "settlement_open": ton_open,
                "treasury_configured": bool(ton_treasury),
                "credits_per_ton": ton_rate if ton_open else None,
                "rate_safe": bool(TON_RATE_MIN <= ton_rate <= TON_RATE_MAX),
            },
            "slh_live": {
                "current_total": internal["slh"]["current_total"],
                "current_live": internal["slh"]["current_live"],
                "current_reserved": internal["slh"]["current_reserved"],
                "legacy_internal": internal["slh"]["legacy_internal"],
                "spendable_live": internal["slh"]["spendable_live"],
                "provenance_status": internal["slh"]["provenance_status"],
            },
        },
        "reconciliation": {
            "stars": stars_status or "UNKNOWN",
            "blockers": blockers,
            "no_inference": True,
        },
    }
