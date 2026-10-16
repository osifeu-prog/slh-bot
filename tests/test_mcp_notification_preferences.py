from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


def test_mcp_notification_tools_use_canonical_control_plane_and_are_owner_only():
    from slh_mcp.auth import Principal
    from slh_mcp.tools import preferences

    owner = Principal(str(OWNER_TELEGRAM_ID), "OWNER", frozenset())
    remote = {
        "ok": True,
        "notification_level": "off",
        "scope": "proactive_progress_updates_only",
    }
    with patch.object(preferences, "current_principal", return_value=owner), patch.object(
        preferences, "is_owner", return_value=True
    ), patch.object(
        preferences.control_plane_client, "set_notification_preference", return_value=remote
    ) as save, patch.object(
        preferences.control_plane_client, "notification_preferences", return_value=remote
    ) as read:
        result = preferences.notifications_set("off")
        assert result["subject"] == str(OWNER_TELEGRAM_ID)
        assert result["notification_level"] == "off"
        assert result["direct_command_replies_muted"] is False
        assert result["critical_security_messages_muted"] is False
        assert preferences.notifications_get()["notification_level"] == "off"
        save.assert_called_once_with("off")
        read.assert_called_once_with()


def test_mcp_notification_tools_reject_missing_principal():
    from slh_mcp.tools import preferences

    with patch.object(preferences, "current_principal", return_value=None):
        try:
            preferences.notifications_get()
        except PermissionError as exc:
            assert str(exc) == "MCP authentication required"
        else:
            raise AssertionError("unauthenticated preferences read was accepted")


def test_mcp_notification_tools_reject_non_owner():
    from slh_mcp.auth import Principal
    from slh_mcp.tools import preferences

    user = Principal("123", "USER", frozenset())
    with patch.object(preferences, "current_principal", return_value=user), patch.object(
        preferences, "is_owner", return_value=False
    ), patch.object(preferences.control_plane_client, "set_notification_preference") as save:
        try:
            preferences.notifications_set("off")
        except PermissionError as exc:
            assert str(exc) == "OWNER_ONLY"
        else:
            raise AssertionError("non-owner could change operator preference")
        save.assert_not_called()


def test_mcp_notification_setting_rejects_unknown_level_without_remote_write():
    from slh_mcp.auth import Principal
    from slh_mcp.tools import preferences

    owner = Principal(str(OWNER_TELEGRAM_ID), "OWNER", frozenset())
    with patch.object(preferences, "current_principal", return_value=owner), patch.object(
        preferences, "is_owner", return_value=True
    ), patch.object(preferences.control_plane_client, "set_notification_preference") as save:
        try:
            preferences.notifications_set("ignore-everything")
        except ValueError as exc:
            assert str(exc) == "NOTIFICATION_LEVEL_INVALID"
        else:
            raise AssertionError("unknown notification level was accepted")
        save.assert_not_called()


def test_mcp_notification_tool_requires_verified_persistence():
    from slh_mcp.auth import Principal
    from slh_mcp.tools import preferences

    owner = Principal(str(OWNER_TELEGRAM_ID), "OWNER", frozenset())
    with patch.object(preferences, "current_principal", return_value=owner), patch.object(
        preferences, "is_owner", return_value=True
    ), patch.object(
        preferences.control_plane_client,
        "set_notification_preference",
        return_value={"ok": False, "notification_level": "milestones"},
    ):
        try:
            preferences.notifications_set("off")
        except RuntimeError as exc:
            assert str(exc) == "CONTROL_PLANE_NOTIFICATION_PREFERENCE_NOT_VERIFIED"
        else:
            raise AssertionError("unverified preference write was accepted")
