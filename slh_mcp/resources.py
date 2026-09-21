"""Safe read-only MCP resources for SLH OS."""

from __future__ import annotations

from core.agent_registry import get_agent, list_agents
from core.authority import get_visible_agents
from core.telegram_token_registry import list_bots

from slh_mcp.auth import authorize, current_principal


_SENSITIVE_AGENT_FIELDS = {"inbox", "history", "permissions", "owner_id"}


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
    return [
        {key: value for key, value in item.items() if key not in _SENSITIVE_AGENT_FIELDS}
        for item in visible.values()
    ]


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
    return {
        key: value for key, value in row.items()
        if key not in _SENSITIVE_AGENT_FIELDS
    }


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


def _resource_system():
    return system_health()


def _resource_agents():
    return agents_resource()


def _resource_agent(agent_id: str):
    return agent_resource(agent_id)


def system_snapshot(principal=None):
    principal = _principal_or_raise(principal)
    from slh_mcp.tools.missions import missions_list
    agents = agents_resource(principal)
    missions = missions_list(principal)
    return {
        "service": "SLH MCP",
        "status": "ok",
        "agent_count": len(agents),
        "mission_count": len(missions),
    }


def _tool_system_snapshot():
    return system_snapshot()


def register_resources(server) -> None:
    server.resource(
        "slh://system",
        name="system",
        description="Safe SLH system metadata.",
    )(_resource_system)
    server.resource(
        "slh://agents",
        name="agents",
        description="Agents visible to the authenticated principal.",
    )(_resource_agents)
    server.resource(
        "slh://agent/{agent_id}",
        name="agent",
        description="One visible SLH agent.",
    )(_resource_agent)


def _tool_system_health():
    return system_health()


def _tool_bots_registry():
    return bot_registry()


def economy_resource(agent_id: str):
    principal = _principal_or_raise()
    from slh_mcp.tools.economy import economy_agent_balance, economy_agent_ledger
    return {
        "balance": economy_agent_balance(principal, agent_id),
        "ledger": economy_agent_ledger(principal, agent_id),
    }


def missions_resource():
    principal = _principal_or_raise()
    from slh_mcp.tools.missions import missions_list
    return missions_list(principal)


def register_extended_resources(server) -> None:
    server.resource(
        "slh://agent/{agent_id}/economy",
        name="agent_economy",
        description="Isolated economy state for one visible agent.",
    )(economy_resource)
    server.resource(
        "slh://missions",
        name="missions",
        description="Safe canonical SLH mission projection.",
    )(missions_resource)


def railway_resource():
    principal = _principal_or_raise()
    if not authorize(principal, "exec.audit"):
        raise PermissionError("RAILWAY_RESOURCE_FORBIDDEN")
    from slh_mcp.tools.integrations import railway_projects
    return {"projects": railway_projects(principal)}


def github_resource():
    principal = _principal_or_raise()
    if not authorize(principal, "exec.audit"):
        raise PermissionError("GITHUB_RESOURCE_FORBIDDEN")
    from slh_mcp.tools.integrations import github_repositories
    return {"repositories": github_repositories(principal)}


def register_infrastructure_resources(server) -> None:
    server.resource(
        "slh://railway",
        name="railway",
        description="Safe Railway project metadata.",
    )(railway_resource)
    server.resource(
        "slh://github",
        name="github",
        description="Safe GitHub repository metadata.",
    )(github_resource)