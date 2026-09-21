"""Agent MCP tools backed by the live SLH Control Plane bridge."""

from __future__ import annotations

from slh_mcp import control_plane_client

_MAX_COMMAND_LENGTH = 2000


def _resolve_principal(principal=None):
    if principal is not None:
        return principal
    from slh_mcp.auth import current_principal

    resolved = current_principal()
    if resolved is None:
        raise PermissionError("MCP authentication required")
    return resolved


def agents_list(principal=None) -> list[dict]:
    principal = _resolve_principal(principal)
    result = control_plane_client.agents(principal.subject)
    return list(result.get("agents", []))


def agents_get(principal, agent_id: str | None = None) -> dict:
    if agent_id is None:
        agent_id, principal = principal, None
    principal = _resolve_principal(principal)
    result = control_plane_client.agent(str(agent_id), principal.subject)
    agent = result.get("agent")
    if not isinstance(agent, dict) or not agent:
        raise KeyError(str(agent_id))
    return dict(agent)


def agents_runtime_status(principal=None) -> dict:
    principal = _resolve_principal(principal)
    return dict(control_plane_client.runtime_status(principal.subject))


def agents_execute(principal, agent_id: str | None = None, command: str | None = None) -> dict:
    principal = _resolve_principal(principal)
    if agent_id is None or command is None:
        raise ValueError("agent_id and command are required")

    command = str(command).strip()
    if not command:
        raise ValueError("command cannot be empty")
    if len(command) > _MAX_COMMAND_LENGTH:
        raise ValueError("command exceeds maximum length")

    return dict(
        control_plane_client.agent_execute(
            str(agent_id),
            command,
            principal.subject,
        )
    )


def _tool_agents_list():
    return agents_list()


def _tool_agents_get(agent_id: str):
    return agents_get(None, agent_id)


def _tool_agents_runtime_status():
    return agents_runtime_status()


def _tool_agents_execute(agent_id: str, command: str):
    return agents_execute(None, agent_id, command)
