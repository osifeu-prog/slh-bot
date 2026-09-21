"""Mission MCP tools backed by canonical MissionLifecycleService."""

from __future__ import annotations

from core.agent_registry import get_agent, list_agents
from core.authority import get_visible_agents
from core.mission_lifecycle import MissionLifecycleService

from slh_mcp.agent_economy import AgentEconomyService


_PUBLIC_FIELDS = {
    "id", "desc", "status", "assigned_to", "reward", "created_at",
    "assigned_at", "execution_started_at", "execution_completed_at", "completed_at",
}
_SERVICE = AgentEconomyService()


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


def complete_agent_mission(
    principal,
    mission_id: str,
    agent_id: str,
    result: dict,
    operation_id: str,
) -> dict:
    principal = _resolve_principal(principal)
    mission_id = str(mission_id).strip()
    agent_id = str(agent_id).strip()
    operation_id = str(operation_id).strip()
    if not mission_id or not agent_id or not operation_id:
        raise ValueError("INVALID_MISSION_COMPLETION_INPUT")
    if not isinstance(result, dict) or not result:
        raise ValueError("MISSION_RESULT_REQUIRED")

    visible = get_visible_agents(principal.subject, list_agents())
    canonical_id, agent = get_agent(agent_id)
    if agent is None or canonical_id not in visible:
        raise PermissionError("AGENT_NOT_VISIBLE")
    if str(principal.role) != "OWNER" and str(agent.get("owner_id")) != str(principal.subject):
        raise PermissionError("AGENT_NOT_OWNED")

    lifecycle = MissionLifecycleService()
    board, _manifest = lifecycle.load_state()
    mission = lifecycle.find_mission(board, mission_id)
    if mission is None:
        raise KeyError(mission_id)
    if str(mission.get("assigned_to")) != agent_id:
        raise PermissionError("MISSION_ASSIGNMENT_MISMATCH")

    reward = float(mission.get("reward", 0) or 0)
    if reward < 0:
        raise ValueError("INVALID_MISSION_REWARD")

    completion = lifecycle.complete_mission(mission_id)
    if completion.get("status") == "blocked":
        refreshed_board, _ = lifecycle.load_state()
        refreshed = lifecycle.find_mission(refreshed_board, mission_id)
        if not isinstance(refreshed, dict) or refreshed.get("status") != "completed":
            return {
                "status": "blocked",
                "mission_id": mission_id,
                "agent_id": agent_id,
                "reason": completion.get("reason", "MISSION_COMPLETION_FAILED"),
            }

    if reward == 0:
        return {
            "status": "completed",
            "mission_id": mission_id,
            "agent_id": agent_id,
            "reward": 0,
            "reward_status": "no_reward",
        }

    try:
        reward_result = _SERVICE.record_reward(
            agent_id=agent_id,
            amount=reward,
            operation_id=operation_id,
            mission_id=mission_id,
            actor=principal.subject,
        )
    except ValueError as exc:
        if str(exc) == "INSUFFICIENT_AGENT_ECONOMY":
            return {
                "status": "reward_pending",
                "mission_id": mission_id,
                "agent_id": agent_id,
                "reward": reward,
                "reason": str(exc),
                "operation_id": operation_id,
            }
        raise

    return {
        "status": "completed",
        "mission_id": mission_id,
        "agent_id": agent_id,
        "reward": reward,
        "reward_status": reward_result.get("status"),
        "operation_id": operation_id,
    }


def _tool_missions_list():
    return missions_list()


def _tool_complete_agent_mission(
    mission_id: str,
    agent_id: str,
    result: dict,
    operation_id: str,
):
    return complete_agent_mission(None, mission_id, agent_id, result, operation_id)
