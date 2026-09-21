"""Safe, read-only MCP resources for SLH OS."""

from __future__ import annotations

from core.telegram_token_registry import list_bots
from slh_mcp.capabilities import list_capabilities


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
    from slh_mcp.tools.agents import agents_list

    return agents_list(principal)


def agent_resource(agent_id: str, principal=None) -> dict:
    principal = _principal_or_raise(principal)
    from slh_mcp.tools.agents import agents_get

    return agents_get(principal, str(agent_id))


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
    from slh_mcp.tools.agents import agents_list
    from slh_mcp.tools.missions import missions_list

    agents = agents_list(principal)
    missions = missions_list(principal)
    return {
        "service": "SLH MCP",
        "status": "ok",
        "agent_count": len(agents),
        "mission_count": len(missions),
    }


def agent_economy_resource(agent_id: str, principal=None) -> dict:
    principal = _principal_or_raise(principal)
    from slh_mcp.tools.economy import economy_agent_balance, economy_agent_ledger

    balance = economy_agent_balance(principal, agent_id)
    ledger = economy_agent_ledger(principal, agent_id)
    return {
        "agent_id": balance["agent_id"],
        "currency": balance["currency"],
        "balance": balance["balance"],
        "ledger_count": len(ledger),
        "recent_ledger": ledger[-20:],
    }


def economy_resource(principal=None) -> dict:
    principal = _principal_or_raise(principal)
    from slh_mcp.agent_economy import AgentEconomyService
    from slh_mcp.tools.agents import agents_list

    service = AgentEconomyService()
    owned_ids = {str(row.get("id")) for row in agents_list(principal)}
    ledger = [
        row for row in service.ledger()
        if str(row.get("account")) in owned_ids
    ]
    return {
        "currency": "agent_credits",
        "treasury_balance": service.balance("AGENT_TREASURY"),
        "visible_agent_count": len(owned_ids),
        "visible_ledger_count": len(ledger),
    }


def missions_resource(principal=None) -> list[dict]:
    principal = _principal_or_raise(principal)
    from slh_mcp.tools.missions import missions_list

    return missions_list(principal)


def railway_resource(principal=None) -> dict:
    principal = _principal_or_raise(principal)
    from slh_mcp.tools.integrations import railway_projects

    return {"projects": railway_projects(principal)}


def github_resource(principal=None) -> dict:
    principal = _principal_or_raise(principal)
    from slh_mcp.tools.integrations import github_repositories

    return {"repositories": github_repositories(principal)}


def capabilities_resource(principal=None) -> list[dict]:
    _principal_or_raise(principal)
    return [
        {
            "name": capability.name,
            "description": capability.description,
            "permission": capability.permission,
            "mutating": capability.mutating,
        }
        for capability in list_capabilities()
    ]


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
            "slh://capabilities",
            "capabilities",
            "SLH MCP capability catalog.",
            lambda: capabilities_resource(),
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