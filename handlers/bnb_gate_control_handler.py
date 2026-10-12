"""Owner-only BNB gate status and force-close control.

This module can only force the public BNB gate CLOSED. It cannot clear a deny
override, open the gate, edit Railway variables, submit transactions, or change
balances. Opening remains governed by the Railway env and canonical proof.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

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


def _mask(value: str) -> str:
    value = str(value or "").strip()
    return f"{value[:6]}...{value[-4:]}" if len(value) >= 10 else (value or "MISSING")


def _authorized_private_uid(message, bot):
    uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
    if not is_owner(uid):
        bot.reply_to(message, "⛔️ הפקודה מיועדת לבעלים בלבד.", parse_mode=None)
        return None
    if str(getattr(getattr(message, "chat", None), "type", "") or "").lower() != "private":
        bot.reply_to(message, "⛔️ שליטת BNB זמינה רק בשיחה הפרטית עם הבוט.", parse_mode=None)
        return None
    return uid


def _status_report() -> str:
    try:
        db = state_manager.load_db()
        if not isinstance(db, dict):
            raise ValueError("DB_INVALID")
        settings = db.get("bsc_settings")
        if settings is None:
            settings = {}
        elif not isinstance(settings, dict):
            raise ValueError("BNB_SETTINGS_INVALID")
        readiness = bnb_readiness(db)
        evidence = _empirical_settlement_evidence(db) or {}
        config = _effective_config(db)
        public_open = bnb_deposits_open()
        override = str(settings.get(_OVERRIDE_KEY) or "").strip().lower() or "(unset)"
        if override not in {"deny", "(unset)", "auto"}:
            override = "UNKNOWN (fails closed)"
        return "\n".join([
            "🔎 BNB GATE — READ ONLY",
            "",
            f"Public gate: {'OPEN' if public_open else 'CLOSED'}",
            f"Env BNB_DEPOSITS_OPEN: {'1' if readiness.get('flag_open') else '0/unset'}",
            f"DB override: {override}",
            f"Readiness: {'PASS' if readiness.get('ready') else 'BLOCKED'}",
            f"Reasons: {', '.join(str(x) for x in (readiness.get('reasons') or [])) or 'none'}",
            f"Empirical evidence: {evidence.get('status') or 'UNKNOWN'}",
            f"Treasury (masked): {_mask(config.get('treasury_wallet'))}",
            "",
            "הבוט יכול לכפות CLOSED בלבד. פתיחה דורשת env=1, מוכנות וראיית chain/ledger תקפה.",
            "Commands: /bnb_gate_status · /bnb_gate_close",
        ])
    except Exception as exc:
        return (
            "🔎 BNB GATE — READ ONLY\n\n"
            f"Public gate: CLOSED (fail-safe; {type(exc).__name__})\n"
            "לא נשלחה עסקה ולא השתנו יתרות."
        )


def _write_deny(*, uid: str) -> dict:
    def mutate(db):
        if not isinstance(db, dict):
            return {"status": "DB_UNREADABLE"}
        if "bsc_settings" not in db:
            db["bsc_settings"] = {}
        settings = db.get("bsc_settings")
        if not isinstance(settings, dict):
            return {"status": "DB_SETTINGS_INVALID"}
        audit = db.get("bnb_gate_override_audit")
        if audit is None:
            audit = []
            db["bnb_gate_override_audit"] = audit
        if not isinstance(audit, list):
            return {"status": "DB_AUDIT_INVALID"}
        settings[_OVERRIDE_KEY] = "deny"
        audit.append({
            "audit_id": uuid.uuid4().hex,
            "uid": str(uid),
            "action": "deny",
            "at": _utc_now().isoformat(),
        })
        del audit[:-100]
        return {"status": "OK", "value": "deny"}

    try:
        result = state_manager.atomic_update(mutate)
    except Exception as exc:
        return {"status": "WRITE_FAILED", "error": type(exc).__name__}
    return result if isinstance(result, dict) else {"status": "WRITE_FAILED"}


def _prepare(uid: str, action: str = "close") -> dict:
    if not is_owner(uid):
        return {"status": "FORBIDDEN"}
    if action != "close":
        return {"status": "INVALID_ACTION"}
    cid = uuid.uuid4().hex[:12]
    _PENDING[cid] = {
        "uid": str(uid),
        "action": "close",
        "expires_at": _utc_now() + timedelta(seconds=_TTL_SECONDS),
    }
    _cleanup_pending()
    return {"status": "PREPARED", "confirmation_id": cid, "action": "close"}


def _confirm(uid: str, cid: str) -> dict:
    if not is_owner(uid):
        return {"status": "FORBIDDEN"}
    record = _PENDING.get(str(cid))
    if not isinstance(record, dict):
        return {"status": "NOT_PENDING"}
    if record.get("uid") != str(uid):
        return {"status": "UID_MISMATCH"}
    if _utc_now() > record["expires_at"]:
        _PENDING.pop(str(cid), None)
        return {"status": "EXPIRED"}
    _PENDING.pop(str(cid), None)

    if record.get("action") != "close":
        return {"status": "INVALID_ACTION"}
    result = _write_deny(uid=uid)
    if result.get("status") != "OK":
        return result
    try:
        persisted = state_manager.load_db()
        settings = persisted.get("bsc_settings") if isinstance(persisted, dict) else None
        if not isinstance(settings, dict) or settings.get(_OVERRIDE_KEY) != "deny":
            return {"status": "INVARIANT_FAILURE_OVERRIDE_NOT_PERSISTED"}
        if bnb_deposits_open():
            return {"status": "INVARIANT_FAILURE_GATE_STILL_OPEN"}
    except Exception:
        return {"status": "INVARIANT_FAILURE_STATE_UNVERIFIED"}
    return {"status": "OK", "public_gate": "CLOSED"}


def _cleanup_pending() -> None:
    now = _utc_now()
    for cid, record in list(_PENDING.items()):
        if not isinstance(record, dict) or record.get("expires_at") < now:
            _PENDING.pop(cid, None)


def register(bot):
    @bot.message_handler(commands=["bnb_gate_status"])
    def bnb_gate_status(message):
        if _authorized_private_uid(message, bot) is None:
            return
        bot.reply_to(message, _status_report(), parse_mode=None)

    @bot.message_handler(commands=["bnb_gate_close"])
    def bnb_gate_close(message):
        uid = _authorized_private_uid(message, bot)
        if uid is None:
            return
        result = _prepare(uid, "close")
        bot.reply_to(
            message,
            "🔎 BNB GATE — תצוגה לפני סגירה כפויה\n\n"
            "לא בוצע שינוי עדיין. באישור ייכתב override=deny למסד הקנוני.\n"
            "השער ייסגר גם אם env=1. אין שליחת TX ואין שינוי יתרות.\n\n"
            f"לאישור תוך 5 דקות:\n/bnb_gate_close_confirm {result['confirmation_id']}",
            parse_mode=None,
        )

    @bot.message_handler(commands=["bnb_gate_close_confirm"])
    def bnb_gate_close_confirm(message):
        uid = _authorized_private_uid(message, bot)
        if uid is None:
            return
        parts = (getattr(message, "text", "") or "").split()
        if len(parts) != 2:
            bot.reply_to(message, "שימוש: /bnb_gate_close_confirm <id>", parse_mode=None)
            return
        result = _confirm(uid, parts[1])
        if result.get("status") == "OK":
            bot.reply_to(
                message,
                "✅ BNB gate override=deny נרשם. השער מאומת כ־CLOSED.\n"
                "🔒 לא נשלחה עסקה ולא השתנו יתרות.",
                parse_mode=None,
            )
        elif result.get("status") == "INVARIANT_FAILURE_GATE_STILL_OPEN":
            bot.reply_to(
                message,
                "🚨 חריגה: נכתב override=deny אך השער עדיין מדווח OPEN. "
                "אל תאפשר הפקדות; נדרשת בדיקת runtime/DB.",
                parse_mode=None,
            )
        elif result.get("status") == "INVARIANT_FAILURE_OVERRIDE_NOT_PERSISTED":
            bot.reply_to(
                message,
                "🚨 לא ניתן לאמת שה-override נשמר. התייחס לשער כלא מאומת וסגור הפקדות עד לבדיקת runtime/DB.",
                parse_mode=None,
            )
        elif result.get("status") == "INVARIANT_FAILURE_STATE_UNVERIFIED":
            bot.reply_to(
                message,
                "🚨 הכתיבה דווחה אך מצב השער לא אומת בקריאה חוזרת. אין להסתמך על הודעה זו כאישור לסגירה; בדוק runtime/DB.",
                parse_mode=None,
            )
        else:
            bot.reply_to(message, f"⛔️ לא בוצע: {result.get('status')}", parse_mode=None)

    print("✅ bnb_gate_control handler registered")
