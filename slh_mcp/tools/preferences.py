"""Per-principal notification preferences through the authenticated Control Plane.

The MCP service must not write its own state/db.json for Telegram preferences:
the bot process owns the canonical database. All reads and writes go through
the authenticated SLH Control Plane bridge.
"""
from __future__ import annotations

from core.authority import is_owner
from slh_mcp import control_plane_client
from slh_mcp.auth import current_principal

_ALLOWED_LEVELS = {"off", "milestones", "all"}


def _subject() -> str:
    principal = current_principal()
    if principal is None or not str(principal.subject).strip():
        raise PermissionError("MCP authentication required")
    subject = str(principal.subject)
    if not is_owner(subject):
        raise PermissionError("OWNER_ONLY")
    return subject


def notifications_get() -> dict:
    """Read only the owner's canonical progress-notification preference."""
    uid = _subject()
    data = control_plane_client.notification_preferences()
    level = str(data.get("notification_level") or "milestones")
    if level not in _ALLOWED_LEVELS:
        raise RuntimeError("CONTROL_PLANE_NOTIFICATION_LEVEL_INVALID")
    return {
        "subject": uid,
        "notification_level": level,
        "allowed_levels": ["off", "milestones", "all"],
        "scope": "proactive_progress_updates_only",
        "direct_command_replies_muted": False,
        "critical_security_messages_muted": False,
    }


def notifications_set(notification_level: str) -> dict:
    """Set only the owner's canonical progress-notification preference."""
    uid = _subject()
    level = str(notification_level or "").strip().lower()
    aliases = {"none": "off", "quiet": "milestones", "important": "milestones", "all_updates": "all"}
    level = aliases.get(level, level)
    if level not in _ALLOWED_LEVELS:
        raise ValueError("NOTIFICATION_LEVEL_INVALID")
    data = control_plane_client.set_notification_preference(level)
    saved = str(data.get("notification_level") or "")
    if data.get("ok") is not True or saved != level:
        raise RuntimeError("CONTROL_PLANE_NOTIFICATION_PREFERENCE_NOT_VERIFIED")
    return {
        "subject": uid,
        "notification_level": saved,
        "scope": "proactive_progress_updates_only",
        "direct_command_replies_muted": False,
        "critical_security_messages_muted": False,
    }


def _tool_notifications_get():
    return notifications_get()


def _tool_notifications_set(notification_level: str):
    return notifications_set(notification_level)
