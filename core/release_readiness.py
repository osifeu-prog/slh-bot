"""Canonical read-only release readiness checks for SLH OS.

This module never mutates state. It is intentionally conservative:
runtime safety gates are validated, while external settlement remains
closed until empirical evidence exists.
"""

from __future__ import annotations

import os


def _check(name, status, detail):
    return {"name": name, "status": status, "detail": detail}


def _telegram_check():
    run_bot = os.getenv("RUN_BOT", "0").strip() == "1"
    token = bool((os.getenv("BOT_TOKEN") or "").strip())
    if run_bot and token:
        return _check("Telegram runtime", "GREEN", "RUN_BOT=1 + BOT_TOKEN configured")
    if run_bot and not token:
        return _check("Telegram runtime", "DEGRADED", "RUN_BOT=1 but BOT_TOKEN is missing; runtime vault fallback may still apply")
    return _check("Telegram runtime", "BLOCKED", "RUN_BOT is not enabled")


def _ai_check():
    try:
        from core.ai_intake import AI_MAX_INPUT_CHARS, normalize_and_chunk

        sample = normalize_and_chunk("x" * 1501)
        if AI_MAX_INPUT_CHARS == 12000 and "[AI_INPUT_CHUNK 1/2]" in sample:
            return _check("AI intake", "GREEN", "canonical 12,000-char bound + chunk normalization active")
        return _check("AI intake", "DEGRADED", f"unexpected intake contract: max={AI_MAX_INPUT_CHARS}")
    except Exception as exc:
        return _check("AI intake", "BLOCKED", f"intake check failed: {type(exc).__name__}")


def _miniapp_auth_check():
    try:
        from core.telegram_webapp_auth import validate_init_data, DEFAULT_MAX_AGE

        if callable(validate_init_data) and int(DEFAULT_MAX_AGE) >= 86400:
            return _check("Mini App auth", "GREEN", "server-side Telegram initData validation is present; max age >=24h")
        return _check("Mini App auth", "DEGRADED", "Telegram validator exists but auth-age contract is unexpected")
    except Exception as exc:
        return _check("Mini App auth", "BLOCKED", f"validator unavailable: {type(exc).__name__}")


def _exchange_check():
    try:
        import state_manager
        from handlers.exchange_handler import _assert_invariants

        db = state_manager.load_db()
        _assert_invariants(db)
        return _check("Internal exchange", "GREEN", "wallet/order reserve invariants pass on canonical db")
    except Exception as exc:
        return _check("Internal exchange", "BLOCKED", f"reserve invariant failed: {type(exc).__name__}")


def _payments_check():
    try:
        from core.revenue_ledger import summary

        data = summary()
        events = int(data.get("events", 0))
        return _check("Stars revenue", "GREEN", f"canonical revenue ledger readable ({events} events)")
    except Exception as exc:
        return _check("Stars revenue", "BLOCKED", f"revenue ledger check failed: {type(exc).__name__}")


def _external_gate_check():
    blockers = []
    notes = []

    # Inspect TON independently so a missing test DB cannot hide a safety violation.
    if os.getenv("TON_DEPOSITS_OPEN", "0").strip() == "1":
        blockers.append("TON_DEPOSITS_OPEN=1; external settlement should remain closed until empirical evidence")

    try:
        from core.bnb_gate import bnb_readiness
        import state_manager

        db = state_manager.load_db()
        bnb = bnb_readiness(db)
        if bool(bnb.get("effective_open")):
            blockers.append("BNB settlement is OPEN before the required empirical deposit smoke")
    except FileNotFoundError:
        notes.append("BNB DB readiness unavailable in this isolated runtime check")
    except Exception as exc:
        notes.append(f"BNB readiness check unavailable: {type(exc).__name__}")

    if blockers:
        return _check("External settlement gates", "BLOCKED", "; ".join(blockers))
    if notes:
        return _check("External settlement gates", "DEGRADED", "; ".join(notes))
    return _check("External settlement gates", "GREEN", "BNB/TON deposits are closed pending empirical evidence")


def _participation_check():
    try:
        from core.participation_policy import activation_status

        status = activation_status()
        if not status["active"]:
            return _check("Participation", "GREEN", "disabled by default; policy/legal/accounting/authority gates remain closed")
        return _check("Participation", "BLOCKED", "ACTIVE while the production policy is not approved for launch")
    except Exception as exc:
        return _check("Participation", "BLOCKED", f"policy check failed: {type(exc).__name__}")


def build_release_report():
    raw = [
        _telegram_check(),
        _ai_check(),
        _miniapp_auth_check(),
        _exchange_check(),
        _payments_check(),
        _external_gate_check(),
        _participation_check(),
    ]
    checks = {row["name"]: row for row in raw}
    blockers = [
        f"{row['name']}: {row['detail']}"
        for row in raw
        if row["status"] == "BLOCKED"
    ]
    degraded = [row for row in raw if row["status"] == "DEGRADED"]
    overall = "BLOCKED" if blockers else ("DEGRADED" if degraded else "GREEN")
    return {"overall_status": overall, "checks": checks, "blockers": blockers}
