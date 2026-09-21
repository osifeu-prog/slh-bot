"""Governed Mission MCP tools backed by canonical MissionLifecycleService."""

from __future__ import annotations

from core.agent_registry import get_agent, list_agents
from core.authority import get_visible_agents
from core.mission_lifecycle import MissionLifecycleService

from slh_mcp.agent_economy import AgentEconomyService


_SERVICE = AgentEconomyService()
_MAX_OPERATION_ID = 128


def _resolve_principal(principal=None):
    if principal is not None:
        return principal
    from slh_mcp.auth import current_principal
    resolved = current_principal()
    if resolved is None:
        raise PermissionError("MCP authentication required")
    return resolved


def missions_list(principal=None) -> list[dict]:
    _resolve_principal(principal)
    board, _manifest = MissionLifecycleService().load_state()
    if not isinstance(board, dict) or board.get("__invalid_state__"):
        raise RuntimeError("mission board unavailable")
    fields = {
        "id", "desc", "status", "assigned_to", "reward", "created_at",
        "assigned_at", "execution_started_at", "execution_completed_at", "completed_at",
    }
    return [
        {key: mission.get(key) for key in fields if key in mission}
        for mission in board.get("missions", [])
        if isinstance(mission, dict)
    ]


def complete_agent_mission(
    principal,
    mission_id: str,
    agent_id: str,
    operation_id: str,
) -> dict:
    principal = _resolve_principal(principal)
    mission_id = str(mission_id).strip()
    agent_id = str(agent_id).strip()
    operation_id = str(operation_id).strip()
    if not mission_id or not agent_id or not operation_id:
        raise ValueError("INVALID_MISSION_COMPLETION_INPUT")
    if len(operation_id) > _MAX_OPERATION_ID:
        raise ValueError("INVALID_OPERATION_ID")

    expected_operation_id = f"mission:{mission_id}:agent_reward"
    if operation_id != expected_operation_id:
        raise ValueError("INVALID_MISSION_OPERATION_ID")

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
    if str(mission.get("assigned_to")) != canonical_id:
        raise PermissionError("MISSION_ASSIGNMENT_MISMATCH")
    if str(mission.get("status")) == "completed":
        # A completed mission is not eligible for a new reward operation.
        # The deterministic operation id prevents an alternate key from re-paying it.
        return {
            "status": "already_completed",
            "mission_id": mission_id,
            "agent_id": canonical_id,
            "reward_status": "already_recorded_or_pending_reconciliation",
            "operation_id": operation_id,
        }
    if str(mission.get("status")) != "executed":
        return {
            "status": "blocked",
            "mission_id": mission_id,
            "agent_id": canonical_id,
            "reason": "MISSION_NOT_EXECUTED",
            "current_status": mission.get("status"),
        }

    reward = float(mission.get("reward", 0) or 0)
    if reward < 0:
        raise ValueError("INVALID_MISSION_REWARD")

    completion = lifecycle.complete_mission(mission_id)
    if completion.get("status") != "completed":
        return {
            "status": "blocked",
            "mission_id": mission_id,
            "agent_id": canonical_id,
            "reason": completion.get("reason", "MISSION_COMPLETION_FAILED"),
            "checks": completion.get("checks"),
        }

    if reward == 0:
        return {
            "status": "completed",
            "mission_id": mission_id,
            "agent_id": canonical_id,
            "reward": 0,
            "reward_status": "no_reward",
            "operation_id": operation_id,
        }

    try:
        reward_result = _SERVICE.record_reward(
            agent_id=canonical_id,
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
                "agent_id": canonical_id,
                "reward": reward,
                "reason": str(exc),
                "operation_id": operation_id,
            }
        raise

    return {
        "status": "completed",
        "mission_id": mission_id,
        "agent_id": canonical_id,
        "reward": reward,
        "reward_status": reward_result.get("status"),
        "operation_id": operation_id,
    }


def _tool_missions_list():
    return missions_list()


def _tool_complete_agent_mission(
    mission_id: str,
    agent_id: str,
    operation_id: str,
):
    return complete_agent_mission(None, mission_id, agent_id, operation_id)
