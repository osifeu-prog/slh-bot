"""Owner-only BNB gate controls.

The DB override is close-only. Opening still requires BNB_DEPOSITS_OPEN=1,
all readiness checks, and revalidated empirical settlement evidence.
No command in this module changes Railway environment variables or sends TXs.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta

import state_manager
from core.authority import is_owner
from core.bnb_gate import (
    _effective_config,
    _empirical_settlement_evidence,
    bnb_deposits_open,
    bnb_readiness,
)

_PENDING: dict[str, dict] = {}
_TTL_SECONDS = 300
_OVERRIDE_KEY = "bnb_deposits_override"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _mask(addr: str) -> str:
    value = str(addr or "").strip()
    return f"{value[:6]}...{value[-4:]}" if len(value) >= 10 else (value or "MISSING")


def _cleanup_pending() -> None:
    now = _utc_now()
    for key in [key for key, item in _PENDING.items() if item["expires_at"] < now]:
        _PENDING.pop(key, None)


def _status_report() -> str:
    try:
        db = state_manager.load_db()
        if not isinstance(db, dict):
            raise RuntimeError("DB_ROOT_INVALID")
        db_status = "READABLE"
        settings = db.get("bsc_settings")
        override = (
            str(settings.get(_OVERRIDE_KEY) or "").strip().lower()
            if isinstance(settings, dict) else ""
        ) or "(unset)"
        readiness = bnb_readiness(db)
        empirical = _empirical_settlement_evidence(db) or {}
        config = _effective_config(db)
        open_now = bnb_deposits_open()
        lines = [
            "🔎 BNB GATE — READ ONLY",
            "",
            f"Public gate: {'OPEN' if open_now else 'CLOSED'}",
            f"DB: {db_status}",
            f"Env BNB_DEPOSITS_OPEN: {os.getenv('BNB_DEPOSITS_OPEN', '(unset)')}",
            f"DB override: {override}",
            f"Readiness: {'PASS' if readiness.get('ready') else 'BLOCKED'}",
            f"Readiness blockers: {', '.join(readiness.get('reasons') or []) or 'none'}",
            f"Empirical status: {empirical.get('status') or 'UNKNOWN'}",
            f"Treasury: {_mask(config.get('treasury_wallet') or '')}",
        ]
    except Exception as exc:
        lines = [
            "🔎 BNB GATE — READ ONLY",
            "",
            "Public gate: CLOSED (fail-safe status; DB/read check failed)",
            f"DB: UNREADABLE ({type(exc).__name__})",
            "No state was changed.",
        ]
    lines += [
        "",
        "Opening still requires env=1, readiness PASS, and revalidated evidence.",
        "This bot can only force-close; /bnb_gate_auto clears the override and env decides.",
        "",
        "Commands:",
        "/bnb_gate_close — prepare forced close",
        "/bnb_gate_auto — prepare removal of close override",
    ]
    return "\n".join(lines)


def _prepare(uid: str, action: str) -> dict:
    if not is_owner(uid):
        return {"status": "FORBIDDEN"}
    if action not in {"close", "auto"}:
        return {"status": "UNKNOWN_ACTION"}
    cid = uuid.uuid4().hex[:12]
    _PENDING[cid] = {
        "uid": str(uid),
        "action": action,
        "expires_at": _utc_now() + timedelta(seconds=_TTL_SECONDS),
    }
    _cleanup_pending()
    return {"status": "PREPARED", "confirmation_id": cid, "action": action}


def _write_override(value, *, uid: str) -> dict:
    def mutate(db):
        if not isinstance(db, dict):
            raise RuntimeError("DB_ROOT_INVALID")
        settings = db.get("bsc_settings")
        if settings is None:
            settings = {}
            db["bsc_settings"] = settings
        if not isinstance(settings, dict):
            raise RuntimeError("BSC_SETTINGS_INVALID")

        if value is None:
            settings.pop(_OVERRIDE_KEY, None)
        else:
            settings[_OVERRIDE_KEY] = value

        audit = db.setdefault("bnb_gate_override_audit", [])
        if not isinstance(audit, list):
            raise RuntimeError("BNB_GATE_AUDIT_INVALID")
        audit.append({
            "audit_id": uuid.uuid4().hex,
            "uid": str(uid),
            "action": value if value is not None else "clear",
            "at": _utc_now().isoformat(),
        })
        del audit[:-100]
        return {"status": "OK", "value": value}

    try:
        return state_manager.atomic_update(mutate)
    except Exception as exc:
        return {"status": "WRITE_FAILED", "error": type(exc).__name__}


def _confirm(uid: str, cid: str) -> dict:
    if not is_owner(uid):
        return {"status": "FORBIDDEN"}
    rec = _PENDING.get(cid)
    if not rec:
        return {"status": "NOT_PENDING"}
    # Validate owner before consuming the token, preventing cross-user invalidation.
    if rec["uid"] != str(uid):
        return {"status": "UID_MISMATCH"}
    _PENDING.pop(cid, None)
    if _utc_now() > rec["expires_at"]:
        return {"status": "EXPIRED"}

    if rec["action"] == "close":
        return _write_override("deny", uid=uid)
    if rec["action"] == "auto":
        return _write_override(None, uid=uid)
    return {"status": "UNKNOWN_ACTION"}


def register(bot):
    @bot.message_handler(commands=["bnb_gate_status"])
    def bnb_gate_status(message):
        uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
        if getattr(getattr(message, "chat", None), "type", None) != "private":
            bot.reply_to(message, "⛔️ Use this command in a private chat.", parse_mode=None)
            return
        if not is_owner(uid):
            bot.reply_to(message, "⛔️ OWNER only.", parse_mode=None)
            return
        bot.reply_to(message, _status_report(), parse_mode=None)

    @bot.message_handler(commands=["bnb_gate_close"])
    def bnb_gate_close(message):
        uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
        if getattr(getattr(message, "chat", None), "type", None) != "private":
            bot.reply_to(message, "⛔️ Use this command in a private chat.", parse_mode=None)
            return
        if not is_owner(uid):
            bot.reply_to(message, "⛔️ OWNER only.", parse_mode=None)
            return
        result = _prepare(uid, "close")
        if result.get("status") != "PREPARED":
            bot.reply_to(message, f"⛔️ {result.get('status')}", parse_mode=None)
            return
        cid = result["confirmation_id"]
        bot.reply_to(
            message,
            "🔎 BNB GATE — preview before forced close\n\n"
            "This writes DB override=deny and forces the public gate closed.\n"
            "No on-chain transaction is sent.\n\n"
            f"Confirm within 5 minutes:\n/bnb_gate_close_confirm {cid}",
            parse_mode=None,
        )

    @bot.message_handler(commands=["bnb_gate_auto"])
    def bnb_gate_auto(message):
        uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
        if getattr(getattr(message, "chat", None), "type", None) != "private":
            bot.reply_to(message, "⛔️ Use this command in a private chat.", parse_mode=None)
            return
        if not is_owner(uid):
            bot.reply_to(message, "⛔️ OWNER only.", parse_mode=None)
            return
        result = _prepare(uid, "auto")
        if result.get("status") != "PREPARED":
            bot.reply_to(message, f"⛔️ {result.get('status')}", parse_mode=None)
            return
        cid = result["confirmation_id"]
        bot.reply_to(
            message,
            "🔎 BNB GATE — preview before clearing override\n\n"
            "This removes the close-only DB override. It does not set env. "
            "If env=1 and every readiness/evidence check passes, the public gate may open.\n\n"
            f"Confirm within 5 minutes:\n/bnb_gate_auto_confirm {cid}",
            parse_mode=None,
        )

    @bot.message_handler(commands=["bnb_gate_close_confirm"])
    def bnb_gate_close_confirm(message):
        if getattr(getattr(message, "chat", None), "type", None) != "private":
            bot.reply_to(message, "⛔️ Use this command in a private chat.", parse_mode=None)
            return
        uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
        parts = (getattr(message, "text", "") or "").split()
        if len(parts) != 2:
            bot.reply_to(message, "Usage: /bnb_gate_close_confirm <id>", parse_mode=None)
            return
        result = _confirm(uid, parts[1])
        if result.get("status") == "OK":
            bot.reply_to(
                message,
                "✅ BNB gate override=deny recorded. Gate evaluation is fail-closed.\n"
                "No TX sent; no balances changed.",
                parse_mode=None,
            )
        else:
            bot.reply_to(message, f"⛔️ {result.get('status')}", parse_mode=None)

    @bot.message_handler(commands=["bnb_gate_auto_confirm"])
    def bnb_gate_auto_confirm(message):
        if getattr(getattr(message, "chat", None), "type", None) != "private":
            bot.reply_to(message, "⛔️ Use this command in a private chat.", parse_mode=None)
            return
        uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
        parts = (getattr(message, "text", "") or "").split()
        if len(parts) != 2:
            bot.reply_to(message, "Usage: /bnb_gate_auto_confirm <id>", parse_mode=None)
            return
        result = _confirm(uid, parts[1])
        if result.get("status") == "OK":
            now_open = bnb_deposits_open()
            bot.reply_to(
                message,
                "✅ Close override cleared; env and all safety checks decide.\n"
                f"Public gate evaluation: {'OPEN' if now_open else 'CLOSED'}\n"
                "No TX sent; no balances changed.",
                parse_mode=None,
            )
        else:
            bot.reply_to(message, f"⛔️ {result.get('status')}", parse_mode=None)
