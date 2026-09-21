"""Safe read-only MCP resources and capability handlers."""

from __future__ import annotations

from core.agent_registry import get_agent, list_agents
from core.authority import get_visible_agents
from core.telegram_token_registry import list_bots

from slh_mcp.auth import current_principal
from slh_mcp.capabilities import bind_handler


def _principal_or_raise(principal=None):
    resolved = principal or current_principal()
    if resolved is None:
        raise PermissionError("MCP authentication required")
    return resolved


def system_health(principal=None) -> dict:
    _principal_or_raise(principal)
    return {"status": "ok", "service": "SLH MCP", "version": "0.1.0"}


def agents_resource(principal=None) -> list[dict]:
    principal = _principal_or_raise(principal)
    visible = get_visible_agents(principal.subject, list_agents())
    return [dict(item) for item in visible.values()]


def agent_resource(agent_id: str, principal=None) -> dict:
    principal = _principal_or_raise(principal)
    visible = get_visible_agents(principal.subject, list_agents())
    key = str(agent_id)
    row = visible.get(key)
    if row is None:
        canonical_id, agent = get_agent(key)
        if agent is None or canonical_id not in visible:
            raise KeyError(key)
        row = visible[canonical_id]
    return dict(row)


def bot_registry(principal=None) -> list[dict]:
    _principal_or_raise(principal)
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


bind_handler("system.health", system_health)
bind_handler("agents.list", agents_resource)
bind_handler("agents.get", agent_resource)
bind_handler("bots.registry", bot_registry)


def register_resources(server) -> None:
    server.resource("slh://system", name="system", description="Safe SLH system metadata.")(system_resource)
    server.resource("slh://agents", name="agents", description="Agents visible to the authenticated principal.")(agents_resource)
    server.resource("slh://agent/{agent_id}", name="agent", description="One visible SLH agent.")(agent_resource)


def system_resource(principal=None):
    return system_health(principal)
