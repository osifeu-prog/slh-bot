"""Safe read-only MCP resources backed by the canonical Control Plane bridge."""

from __future__ import annotations

from core.telegram_token_registry import list_bots

from slh_mcp import control_plane_client
from slh_mcp.auth import current_principal



def _principal(principal=None):
    value = principal or current_principal()
    if value is None:
        raise PermissionError("MCP authentication required")
    return value


def system_health(principal=None) -> dict:
    principal = _principal(principal)
    result = control_plane_client._request("/api/internal/mcp/system", principal=principal.subject)
    return {
        "status": result.get("status"),
        "service": result.get("service"),
        "agent_count": result.get("agent_count"),
        "mission_count": result.get("mission_count"),
    }


def agents_resource(principal=None) -> list[dict]:
    principal = _principal(principal)
    result = control_plane_client.agents(principal.subject)
    return list(result.get("agents", []))


def agent_resource(agent_id: str, principal=None) -> dict:
    principal = _principal(principal)
    result = control_plane_client.agent(str(agent_id), principal.subject)
    agent = result.get("agent")
    if not isinstance(agent, dict):
        raise KeyError(str(agent_id))
    return agent


def bot_registry(principal=None) -> list[dict]:
    _principal(principal)
    result = []
    for item in list_bots():
        result.append({
            "alias": item.get("alias"),
            "username": item.get("username"),
            "label": item.get("label"),
            "targets": [
                {
                    "project": target.get("project"),
                    "project_id": target.get("project_id"),
                    "environment": target.get("environment"),
                    "service": target.get("service"),
                    "service_id": target.get("service_id"),
                    "variable": target.get("variable"),
                }
                for target in item.get("targets", [])
            ],
        })
    return result


def _tool_system_health():
    return system_health()


def _tool_bots_registry():
    return bot_registry()


def register_resources(server) -> None:
    server.resource(
        "slh://system",
        name="system",
        description="Safe SLH system metadata.",
    )(_tool_system_health)
    server.resource(
        "slh://agents",
        name="agents",
        description="Agents visible to the authenticated principal.",
    )(agents_resource)
    server.resource(
        "slh://agent/{agent_id}",
        name="agent",
        description="One visible SLH agent.",
    )(agent_resource)
