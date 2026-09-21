"""Mission MCP tools backed by the canonical MissionLifecycleService."""

from __future__ import annotations

from core.mission_lifecycle import MissionLifecycleService


_PUBLIC_FIELDS = {
    "id", "desc", "status", "assigned_to", "reward", "created_at",
    "assigned_at", "execution_started_at", "execution_completed_at", "completed_at",
}


def _resolve_principal(principal=None):
    if principal is not None:
        return principal
    from slh_mcp.auth import current_principal
    resolved = current_principal()
    if resolved is None:
        raise PermissionError("MCP authentication required")
    return resolved


def _public_mission(mission: dict) -> dict:
    return {key: mission.get(key) for key in _PUBLIC_FIELDS if key in mission}


def missions_list(principal=None) -> list[dict]:
    _resolve_principal(principal)
    board, _manifest = MissionLifecycleService().load_state()
    if not isinstance(board, dict) or board.get("__invalid_state__"):
        raise RuntimeError("mission board unavailable")
    return [_public_mission(m) for m in board.get("missions", []) if isinstance(m, dict)]

def _tool_missions_list():
    return missions_list()
