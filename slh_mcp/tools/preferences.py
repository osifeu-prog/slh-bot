"""Per-principal notification preferences exposed through authenticated MCP."""

from __future__ import annotations

from core.ui_preferences import get_preferences, set_preferences, validate_notification_level
from slh_mcp.auth import current_principal


def _subject():
    principal = current_principal()
    if principal is None or not str(principal.subject).strip():
        raise PermissionError("MCP authentication required")
    return str(principal.subject)


def notifications_get() -> dict:
    """Read only the authenticated principal's own notification preferences."""
    uid = _subject()
    prefs = get_preferences(uid)
    return {
        "subject": uid,
        "notification_level": prefs["notification_level"],
        "allowed_levels": ["off", "milestones", "all"],
        "scope": "proactive_progress_updates_only",
    }


def notifications_set(notification_level: str) -> dict:
    """Update only the authenticated principal's own notification preferences."""
    uid = _subject()
    level = validate_notification_level(notification_level)
    prefs = set_preferences(uid, notification_level=level)
    return {
        "subject": uid,
        "notification_level": prefs["notification_level"],
        "scope": "proactive_progress_updates_only",
        "direct_command_replies_muted": False,
        "critical_security_messages_muted": False,
    }


def _tool_notifications_get():
    return notifications_get()


def _tool_notifications_set(notification_level: str):
    return notifications_set(notification_level)
