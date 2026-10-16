"""MCP tools for the authenticated operator notification preference."""
from __future__ import annotations

from slh_mcp import control_plane_client


def _tool_notification_preferences() -> dict:
    """Read the configured principal's notification preference via Control Plane."""
    return control_plane_client.notification_preferences()


def _tool_set_progress_notifications(progress_updates_enabled: bool) -> dict:
    """Enable or suppress non-critical progress updates; never suppress critical alerts."""
    if not isinstance(progress_updates_enabled, bool):
        raise ValueError("BOOLEAN_REQUIRED")
    return control_plane_client.set_progress_notifications(progress_updates_enabled)
