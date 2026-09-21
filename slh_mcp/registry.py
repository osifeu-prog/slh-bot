"""Explicit MCP capability and resource registration."""

from __future__ import annotations

from slh_mcp.capabilities import guarded_handler, list_capabilities
from slh_mcp.resources import (
    register_economic_resources,
    register_extended_resources,
    register_infrastructure_resources,
    register_resources,
    _tool_bots_registry,
    _tool_system_health,
    _tool_system_snapshot,
)
from slh_mcp.tools.bots import _tool_bots_federation
from slh_mcp.tools.agent_state import _tool_agents_consistency
from slh_mcp.tools.agents import (
    _tool_agents_execute,
    _tool_agents_get,
    _tool_agents_list,
    _tool_agents_runtime_status,
)
from slh_mcp.tools.missions import _tool_complete_agent_mission, _tool_missions_list
from slh_mcp.tools.integrations import (
    _tool_github_ci_status,
    _tool_github_repositories,
    _tool_railway_deployments,
    _tool_railway_projects,
    _tool_railway_services,
)
from slh_mcp.tools.economic_ledger import _tool_economy_ledger
from slh_mcp.tools.mqtt import _tool_mqtt_status, _tool_mqtt_probe
from slh_mcp.tools.economy import (
    _tool_economy_agent_balance,
    _tool_economy_agent_ledger,
    _tool_economy_commit_transfer,
    _tool_economy_propose_transfer,
)


def register_capabilities(server):
    handlers = {
        "system.health": _tool_system_health,
        "system.snapshot": _tool_system_snapshot,
        "agents.list": _tool_agents_list,
        "agents.get": _tool_agents_get,
        "agents.runtime_status": _tool_agents_runtime_status,
        "agents.consistency": _tool_agents_consistency,
        "agents.execute": _tool_agents_execute,
        "missions.list": _tool_missions_list,
        "missions.complete": _tool_complete_agent_mission,
        "economy.agent_balance": _tool_economy_agent_balance,
        "economy.agent_ledger": _tool_economy_agent_ledger,
        "economy.ledger": _tool_economy_ledger,
        "economy.propose_transfer": _tool_economy_propose_transfer,
        "economy.commit_transfer": _tool_economy_commit_transfer,
        "bots.registry": _tool_bots_registry,
        "bots.federation": _tool_bots_federation,
        "mqtt.status": _tool_mqtt_status,
        "mqtt.probe": _tool_mqtt_probe,
        "railway.projects": _tool_railway_projects,
        "railway.services": _tool_railway_services,
        "railway.deployments": _tool_railway_deployments,
        "github.repositories": _tool_github_repositories,
        "github.ci_status": _tool_github_ci_status,
    }

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
    register_economic_resources(server)
    register_infrastructure_resources(server)
    from slh_mcp.resources import register_mqtt_resources
    register_mqtt_resources(server)
    return server