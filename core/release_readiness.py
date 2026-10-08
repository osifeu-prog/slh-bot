"""Canonical read-only release readiness checks for SLH OS.

This module never mutates state. It is intentionally conservative:
runtime safety gates are validated. BNB remains closed until empirical
evidence exists; TON may be public-open when its canonical readiness
contract is valid.
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
        from core.system_checks import check_exchange

        result = check_exchange()
        public_ready = bool(result.get("public_ready"))
        verdict = str(result.get("verdict") or "")
        detail = str(result.get("detail") or "")

        if public_ready and verdict == "OPEN":
            return _check("Internal exchange", "GREEN", "public trading gate OPEN; canonical exchange readiness PASS")

        if public_ready and verdict == "READY_TO_OPEN":
            return _check("Internal exchange", "DEGRADED", "public state clean but trading gate is CLOSED")

        return _check(
            "Internal exchange",
            "BLOCKED",
            detail or f"exchange readiness verdict: {verdict or 'UNKNOWN'}",
        )
    except Exception as exc:
        return _check("Internal exchange", "BLOCKED", f"exchange readiness check failed: {type(exc).__name__}")


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
    degraded = []
    notes = []

    # TON is allowed to be public-open when its own readiness contract is valid.
    if os.getenv("TON_DEPOSITS_OPEN", "0").strip() == "1":
        try:
            from core.ton_deposit_service import ton_readiness

            ton = ton_readiness()
            if not bool(ton.get("effective_open")):
                blockers.append("TON_DEPOSITS_OPEN=1 but TON readiness is not effective")
            else:
                notes.append("TON settlement PUBLIC OPEN; canonical readiness contract is valid")
        except Exception as exc:
            blockers.append(f"TON readiness unavailable: {type(exc).__name__}")

    try:
        from core.bnb_gate import bnb_readiness
        import state_manager

        db = state_manager.load_db()
        bnb = bnb_readiness(db)
        if bool(bnb.get("effective_open")):
            blockers.append("BNB settlement is OPEN before the required empirical deposit smoke")
    except FileNotFoundError:
        degraded.append("BNB DB readiness unavailable in this isolated runtime check")
    except Exception as exc:
        degraded.append(f"BNB readiness check unavailable: {type(exc).__name__}")

    if blockers:
        detail = "; ".join(blockers + notes + degraded)
        return _check("External settlement gates", "BLOCKED", detail)
    if degraded:
        detail = "; ".join(notes + degraded)
        return _check("External settlement gates", "DEGRADED", detail)
    detail = "; ".join(notes) or "BNB settlement remains closed pending empirical evidence"
    return _check("External settlement gates", "GREEN", detail)


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
