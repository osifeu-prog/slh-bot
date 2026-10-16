from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


def test_mcp_notification_tools_are_scoped_to_authenticated_principal():
    from slh_mcp import tools
    from slh_mcp.auth import Principal
    from slh_mcp.tools import preferences

    owner = Principal(str(OWNER_TELEGRAM_ID), "OWNER", frozenset())
    db = {"ui_preferences": {}}

    with patch.object(preferences, "current_principal", return_value=owner), patch(
        "core.ui_preferences.state_manager.load_db", return_value=db
    ), patch(
        "core.ui_preferences.state_manager.atomic_update",
        side_effect=lambda mutate: mutate(db),
    ):
        result = preferences.notifications_set("off")
        assert result["subject"] == str(OWNER_TELEGRAM_ID)
        assert result["notification_level"] == "off"
        assert result["direct_command_replies_muted"] is False
        assert preferences.notifications_get()["notification_level"] == "off"
        assert db["ui_preferences"][str(OWNER_TELEGRAM_ID)]["notification_level"] == "off"


def test_mcp_notification_tools_reject_missing_principal():
    from slh_mcp.tools import preferences

    with patch.object(preferences, "current_principal", return_value=None):
        try:
            preferences.notifications_get()
        except PermissionError as exc:
            assert str(exc) == "MCP authentication required"
        else:
            raise AssertionError("unauthenticated preferences read was accepted")


def test_mcp_notification_setting_rejects_unknown_level():
    from slh_mcp.auth import Principal
    from slh_mcp.tools import preferences

    owner = Principal(str(OWNER_TELEGRAM_ID), "OWNER", frozenset())
    with patch.object(preferences, "current_principal", return_value=owner):
        try:
            preferences.notifications_set("ignore-everything")
        except ValueError as exc:
            assert str(exc) == "NOTIFICATION_LEVEL_INVALID"
        else:
            raise AssertionError("unknown notification level was accepted")
