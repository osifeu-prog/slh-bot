"""Mission MCP tools backed by the canonical Control Plane bridge."""

from __future__ import annotations

from slh_mcp import control_plane_client
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
    principal = _resolve_principal(principal)
    result = control_plane_client.missions(principal.subject)
    return list(result.get("missions", []))


def complete_agent_mission(
    principal,
    mission_id: str,
    agent_id: str,
    result: dict | None,
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
    if result is not None and not isinstance(result, dict):
        raise ValueError("MISSION_RESULT_INVALID")

    mission_result = control_plane_client.mission(
        mission_id,
        principal.subject,
    )
    mission = mission_result.get("mission") or {}
    if not mission:
        raise KeyError(mission_id)
    if str(mission.get("assigned_to")) != agent_id:
        raise PermissionError("MISSION_ASSIGNMENT_MISMATCH")

    status = str(mission.get("status", "")).lower()
    if status == "completed":
        return {
            "status": "already_completed",
            "mission_id": mission_id,
            "agent_id": agent_id,
            "reward_status": "already_recorded_or_pending_reconciliation",
            "operation_id": operation_id,
        }
    if status != "executed":
        return {
            "status": "blocked",
            "mission_id": mission_id,
            "agent_id": agent_id,
            "reason": "MISSION_NOT_EXECUTED",
            "current_status": mission.get("status"),
        }

    reward = float(mission.get("reward", 0) or 0)
    if reward < 0:
        raise ValueError("INVALID_MISSION_REWARD")

    completion = control_plane_client.mission_complete(
        mission_id,
        principal.subject,
    )
    if completion.get("status") != "completed":
        return {
            "status": "blocked",
            "mission_id": mission_id,
            "agent_id": agent_id,
            "reason": completion.get(
                "reason",
                "MISSION_COMPLETION_FAILED",
            ),
        }

    if reward == 0:
        return {
            "status": "completed",
            "mission_id": mission_id,
            "agent_id": agent_id,
            "reward": 0,
            "reward_status": "no_reward",
            "operation_id": operation_id,
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
    result: dict | None,
    operation_id: str,
):
    return complete_agent_mission(
        None,
        mission_id,
        agent_id,
        result,
        operation_id,
    )
