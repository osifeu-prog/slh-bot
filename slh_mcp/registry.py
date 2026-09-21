"""Explicit MCP capability and resource registration."""

from __future__ import annotations

from slh_mcp.capabilities import guarded_handler, list_capabilities
from slh_mcp.resources import register_extended_resources, register_resources
from slh_mcp.tools.agents import (
    _tool_agents_execute,
    _tool_agents_get,
    _tool_agents_list,
    _tool_agents_runtime_status,
)
from slh_mcp.tools.missions import _tool_complete_agent_mission, _tool_missions_list
from slh_mcp.tools.integrations import (
    _tool_railway_projects,
    _tool_railway_services,
    _tool_railway_deployments,
    _tool_github_repositories,
    _tool_github_ci_status,
)
from slh_mcp.tools.economy import (
    _tool_economy_agent_balance,
    _tool_economy_agent_ledger,
    _tool_economy_propose_transfer,
    _tool_economy_commit_transfer,
)


def register_capabilities(server):
    handlers = {
        "agents.list": _tool_agents_list,
        "agents.get": _tool_agents_get,
        "agents.runtime_status": _tool_agents_runtime_status,
        "agents.execute": _tool_agents_execute,
        "missions.list": _tool_missions_list,
        "missions.complete": _tool_complete_agent_mission,
        "railway.projects": _tool_railway_projects,
        "railway.services": _tool_railway_services,
        "railway.deployments": _tool_railway_deployments,
        "github.repositories": _tool_github_repositories,
        "github.ci_status": _tool_github_ci_status,
        "missions.complete": _tool_complete_agent_mission,
        "economy.agent_balance": _tool_economy_agent_balance,
        "economy.agent_ledger": _tool_economy_agent_ledger,
        "economy.propose_transfer": _tool_economy_propose_transfer,
        "economy.commit_transfer": _tool_economy_commit_transfer,
    }

    from slh_mcp.resources import (
        _tool_system_health,
        _tool_bots_registry,
    )
    handlers["system.health"] = _tool_system_health
    handlers["bots.registry"] = _tool_bots_registry

    for capability in list_capabilities():
        handler = handlers.get(capability.name)
        if handler is None:
            continue
        server.add_tool(
            guarded_handler(capability, handler),
            name=capability.name,
            description=capability.description,
        )
    register_resources(server)
    register_extended_resources(server)
    return server