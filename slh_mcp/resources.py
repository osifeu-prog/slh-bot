"""Safe, read-only MCP resources for SLH OS."""

from __future__ import annotations

from core.agent_registry import get_agent, list_agents
from core.authority import get_visible_agents
from core.telegram_token_registry import list_bots


_SENSITIVE_AGENT_FIELDS = {"inbox", "history", "permissions", "owner_id"}


def _principal_or_raise(principal=None):
    if principal is not None:
        return principal
    from slh_mcp.auth import current_principal

    resolved = current_principal()
    if resolved is None:
        raise PermissionError("MCP authentication required")
    return resolved


def system_health(principal=None) -> dict:
    _principal_or_raise(principal)
    return {
        "status": "ok",
        "service": "SLH MCP",
        "version": "0.1.0",
    }


def agents_resource(principal=None) -> list[dict]:
    principal = _principal_or_raise(principal)
    visible = get_visible_agents(principal.subject, list_agents())
    return [
        {
            key: value
            for key, value in item.items()
            if key not in _SENSITIVE_AGENT_FIELDS
        }
        for item in visible.values()
    ]


def agent_resource(agent_id: str, principal=None) -> dict:
    principal = _principal_or_raise(principal)
    visible = get_visible_agents(principal.subject, list_agents())
    canonical_id, agent = get_agent(str(agent_id))
    if agent is None or canonical_id not in visible:
        raise KeyError(str(agent_id))
    return {
        key: value
        for key, value in visible[canonical_id].items()
        if key not in _SENSITIVE_AGENT_FIELDS
    }


def bot_registry(principal=None) -> list[dict]:
    _principal_or_raise(principal)
    result = []
    for item in list_bots():
        result.append(
            {
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
            }
        )
    return result


def system_snapshot(principal=None) -> dict:
    principal = _principal_or_raise(principal)
    missions = missions_resource(principal)
    agents = agents_resource(principal)
    return {
        "service": "SLH MCP",
        "status": "ok",
        "agent_count": len(agents),
        "mission_count": len(missions),
    }


def agent_economy_resource(agent_id: str, principal=None) -> dict:
    principal = _principal_or_raise(principal)
    from slh_mcp.agent_economy import AgentEconomyService

    visible = get_visible_agents(principal.subject, list_agents())
    canonical_id, agent = get_agent(str(agent_id))
    if agent is None or canonical_id not in visible:
        raise KeyError(str(agent_id))

    service = AgentEconomyService()
    rows = [
        row
        for row in service.ledger()
        if row.get("account") == canonical_id
    ]
    return {
        "agent_id": canonical_id,
        "currency": "agent_credits",
        "balance": service.balance(canonical_id),
        "ledger_count": len(rows),
        "recent_ledger": rows[-20:],
    }


def economy_resource(principal=None) -> dict:
    principal = _principal_or_raise(principal)
    from slh_mcp.agent_economy import AgentEconomyService

    service = AgentEconomyService()
    visible_agents = get_visible_agents(principal.subject, list_agents())
    owned_ids = set(visible_agents)
    agent_rows = [
        row
        for row in service.ledger()
        if row.get("account") in owned_ids
    ]
    return {
        "currency": "agent_credits",
        "treasury_balance": service.balance("AGENT_TREASURY"),
        "visible_agent_count": len(owned_ids),
        "visible_ledger_count": len(agent_rows),
    }


def missions_resource(principal=None) -> list[dict]:
    principal = _principal_or_raise(principal)
    from slh_mcp.tools.missions import missions_list

    return missions_list(principal)


def railway_resource(principal=None) -> dict:
    principal = _principal_or_raise(principal)
    from slh_mcp.tools.integrations import railway_projects

    return {
        "projects": railway_projects(principal),
    }


def github_resource(principal=None) -> dict:
    principal = _principal_or_raise(principal)
    from slh_mcp.tools.integrations import github_repositories

    return {
        "repositories": github_repositories(principal),
    }


def bots_federation_resource(principal=None) -> list[dict]:
    principal = _principal_or_raise(principal)
    from slh_mcp.tools.bots import bots_federation

    return bots_federation(principal)


def register_resources(server) -> None:
    registrations = (
        (
            "slh://system",
            "system",
            "Safe SLH system metadata.",
            lambda: system_health(),
        ),
        (
            "slh://agents",
            "agents",
            "Agents visible to the authenticated principal.",
            lambda: agents_resource(),
        ),
        (
            "slh://agent/{agent_id}",
            "agent",
            "One visible SLH agent.",
            lambda agent_id: agent_resource(agent_id),
        ),
        (
            "slh://agent/{agent_id}/economy",
            "agent_economy",
            "Isolated economy state for one visible agent.",
            lambda agent_id: agent_economy_resource(agent_id),
        ),
        (
            "slh://missions",
            "missions",
            "Safe canonical SLH mission projection.",
            lambda: missions_resource(),
        ),
        (
            "slh://economy",
            "economy",
            "Safe isolated Agent Economy summary.",
            lambda: economy_resource(),
        ),
        (
            "slh://railway",
            "railway",
            "Safe Railway project metadata.",
            lambda: railway_resource(),
        ),
        (
            "slh://github",
            "github",
            "Safe GitHub repository metadata.",
            lambda: github_resource(),
        ),
        (
            "slh://bots",
            "bots",
            "Federated SLH bot and deployment read model.",
            lambda: bots_federation_resource(),
        ),
    )

    for uri, name, description, handler in registrations:
        server.resource(
            uri,
            name=name,
            description=description,
        )(handler)


def _tool_system_health():
    return system_health()


def _tool_system_snapshot():
    return system_snapshot()


def _tool_bots_registry():
    return bot_registry()
