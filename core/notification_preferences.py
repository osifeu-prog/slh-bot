"""Per-user delivery preferences for non-critical workflow progress messages.

Direct command replies, security incidents, payment receipts, financial gate
failures and action-required notices must never be suppressed by this preference.
"""
from __future__ import annotations

import state_manager

_ALLOWED_KINDS = {"progress", "milestone", "routine_status"}
_CRITICAL_KINDS = {"security", "financial", "payment", "gate_failure", "action_required"}


def get_notification_preferences(uid: str) -> dict:
    uid = str(uid or "").strip()
    if not uid.isdigit():
        return {"ok": False, "error": "INVALID_USER_ID"}
    try:
        db = state_manager.load_db()
    except Exception:
        return {"ok": False, "error": "STATE_UNAVAILABLE"}
    users = db.get("users", {})
    user = users.get(uid) if isinstance(users, dict) else None
    if not isinstance(user, dict):
        return {"ok": False, "error": "USER_NOT_FOUND"}
    prefs = user.get("notification_preferences", {})
    prefs = prefs if isinstance(prefs, dict) else {}
    return {
        "ok": True,
        "progress_updates_enabled": prefs.get("progress_updates_enabled") is not False,
        "critical_alerts_enabled": True,
        "scope": "proactive_noncritical_progress_only",
    }


def set_progress_updates(uid: str, enabled: bool) -> dict:
    uid = str(uid or "").strip()
    if not uid.isdigit():
        return {"ok": False, "error": "INVALID_USER_ID"}
    if not isinstance(enabled, bool):
        return {"ok": False, "error": "BOOLEAN_REQUIRED"}

    def mutate(db):
        users = db.get("users", {})
        user = users.get(uid) if isinstance(users, dict) else None
        if not isinstance(user, dict):
            return {"ok": False, "error": "USER_NOT_FOUND"}
        prefs = user.setdefault("notification_preferences", {})
        if not isinstance(prefs, dict):
            raise ValueError("NOTIFICATION_PREFERENCES_INVALID")
        prefs["progress_updates_enabled"] = enabled
        return {
            "ok": True,
            "progress_updates_enabled": enabled,
            "critical_alerts_enabled": True,
            "scope": "proactive_noncritical_progress_only",
        }

    try:
        return state_manager.atomic_update(mutate)
    except Exception:
        return {"ok": False, "error": "NOTIFICATION_PREFERENCE_SAVE_FAILED"}


def should_send_notification(uid: str, kind: str) -> bool:
    """Fail open for critical messages, fail closed for optional progress messages."""
    category = str(kind or "").strip().lower()
    if category in _CRITICAL_KINDS or category not in _ALLOWED_KINDS:
        return True
    prefs = get_notification_preferences(uid)
    # If preference state cannot be trusted, avoid suppressing any message.
    if not prefs.get("ok"):
        return True
    return prefs.get("progress_updates_enabled") is True


def send_progress_update(bot, uid: str, text: str, *, kind: str = "progress", **kwargs) -> bool:
    """Send an optional proactive update only when the recipient has opted in."""
    if not should_send_notification(uid, kind):
        return False
    bot.send_message(uid, str(text), **kwargs)
    return True
