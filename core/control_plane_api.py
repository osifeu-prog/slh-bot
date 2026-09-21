"""Internal canonical Control Plane API functions used by web and MCP.

This module owns no HTTP transport. It exposes typed operations over the
canonical agent registry, runtime, mission lifecycle and agent economy.
"""
from __future__ import annotations

import os
import hmac

from core.agent_registry import get_agent, list_agents
from core.authority import get_visible_agents, has_permission
from core.mission_lifecycle import MissionLifecycleService
from core.runtime_service import execute_agent, status as runtime_status

from core.agent_economy import AgentEconomyService

_ECONOMY_SERVICE = AgentEconomyService()
_SENSITIVE_AGENT_FIELDS = {"inbox", "history", "permissions", "owner_id"}


def authorize_internal(supplied_key: str, principal_id: str, permission: str) -> bool:
    expected = str(os.getenv("SLH_CORE_INTERNAL_KEY", "")).strip()
    supplied_key = str(supplied_key or "").strip()
    principal_id = str(principal_id or "").strip()
    if not expected or not supplied_key or not principal_id:
        return False
    if not hmac.compare_digest(supplied_key, expected):
        return False
    return has_permission(principal_id, permission)


def _public_agent(agent: dict) -> dict:
    return {k: v for k, v in agent.items() if k not in _SENSITIVE_AGENT_FIELDS}


def list_agents_control(principal_id: str) -> list[dict]:
    visible = get_visible_agents(str(principal_id), list_agents())
    return [_public_agent(item) for item in visible.values()]


def get_agent_control(principal_id: str, agent_id: str) -> dict:
    visible = get_visible_agents(str(principal_id), list_agents())
    canonical_id, agent = get_agent(str(agent_id))
    if agent is None or canonical_id not in visible:
        raise KeyError(str(agent_id))
    return _public_agent(visible[canonical_id])


def runtime_status_control(principal_id: str) -> dict:
    if not has_permission(principal_id, "agents.view_all"):
        raise PermissionError("RUNTIME_STATUS_FORBIDDEN")
    snapshot = runtime_status()
    return {
        "state": snapshot.get("state"),
        "running": snapshot.get("running"),
        "boot_ok": snapshot.get("boot_ok"),
        "queue_size": snapshot.get("queue_size"),
        "thread_alive": snapshot.get("thread_alive"),
        "agent_count": len(snapshot.get("agents", [])),
    }


def execute_agent_control(principal_id: str, agent_id: str, command: str) -> dict:
    visible = get_visible_agents(str(principal_id), list_agents())
    canonical_id, agent = get_agent(str(agent_id))
    if agent is None or canonical_id not in visible:
        raise KeyError(str(agent_id))
    command = str(command).strip()
    if not command or len(command) > 2000:
        raise ValueError("INVALID_AGENT_COMMAND")
    return execute_agent(canonical_id, command, source="control_plane")


def missions_list_control(principal_id: str) -> list[dict]:
    if not has_permission(principal_id, "public.view"):
        raise PermissionError("MISSIONS_FORBIDDEN")
    board, _manifest = MissionLifecycleService().load_state()
    if not isinstance(board, dict) or board.get("__invalid_state__"):
        raise RuntimeError("MISSION_BOARD_UNAVAILABLE")
    allowed = {
        "id", "desc", "status", "assigned_to", "reward", "created_at",
        "assigned_at", "execution_started_at", "execution_completed_at", "completed_at",
    }
    return [
        {k: m.get(k) for k in allowed if k in m}
        for m in board.get("missions", [])
        if isinstance(m, dict)
    ]


def mission_control(principal_id: str, mission_id: str) -> dict:
    missions = missions_list_control(principal_id)
    for mission in missions:
        if str(mission.get("id")) == str(mission_id):
            return mission
    raise KeyError(str(mission_id))


def mission_complete_control(principal_id: str, mission_id: str) -> dict:
    if not has_permission(principal_id, "agents.manage"):
        raise PermissionError("MISSION_COMPLETE_FORBIDDEN")
    return MissionLifecycleService().complete_mission(str(mission_id))


def _owned_agent(principal_id: str, agent_id: str) -> bool:
    visible = get_visible_agents(str(principal_id), list_agents())
    canonical_id, agent = get_agent(str(agent_id))
    if agent is None or canonical_id not in visible:
        return False
    role = str(__import__("core.authority", fromlist=["get_role"]).get_role(principal_id))
    return role in {"OWNER", "MCP_SERVICE", "ADMIN", "DEVELOPER"} or str(agent.get("owner_id")) == str(principal_id)


def economy_balance_control(principal_id: str, agent_id: str) -> dict:
    if not _owned_agent(principal_id, agent_id):
        raise PermissionError("AGENT_NOT_OWNED")
    return {
        "agent_id": str(agent_id),
        "balance": _ECONOMY_SERVICE.balance(str(agent_id)),
        "currency": "agent_credits",
    }


def economy_ledger_control(principal_id: str, agent_id: str, limit: int = 100) -> list[dict]:
    if not _owned_agent(principal_id, agent_id):
        raise PermissionError("AGENT_NOT_OWNED")
    limit = int(limit)
    if limit < 1 or limit > 500:
        raise ValueError("INVALID_LIMIT")
    rows = [row for row in _ECONOMY_SERVICE.ledger() if row.get("account") == str(agent_id)]
    return rows[-limit:]


def economy_propose_control(principal_id: str, source_agent: str, target_agent: str, amount, operation_id: str, reason: str) -> dict:
    if not _owned_agent(principal_id, source_agent):
        raise PermissionError("SOURCE_AGENT_NOT_OWNED")
    return _ECONOMY_SERVICE.propose_transfer(
        source_agent=source_agent,
        target_agent=target_agent,
        amount=amount,
        operation_id=operation_id,
        actor=principal_id,
        reason=reason,
    )


def economy_transfer_control(principal_id: str, source_agent: str, target_agent: str, amount, operation_id: str, reason: str) -> dict:
    if not _owned_agent(principal_id, source_agent):
        raise PermissionError("SOURCE_AGENT_NOT_OWNED")
    return _ECONOMY_SERVICE.transfer(
        source_agent=source_agent,
        target_agent=target_agent,
        amount=amount,
        operation_id=operation_id,
        actor=principal_id,
        reason=reason,
    )


def economy_reward_control(principal_id: str, agent_id: str, amount, operation_id: str, mission_id: str) -> dict:
    if not has_permission(principal_id, "agents.manage"):
        raise PermissionError("REWARD_FORBIDDEN")
    return _ECONOMY_SERVICE.record_reward(
        agent_id=agent_id,
        amount=amount,
        operation_id=operation_id,
        mission_id=mission_id,
        actor=principal_id,
    )
