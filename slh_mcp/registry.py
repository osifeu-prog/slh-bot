"""Explicit MCP capability and resource registration."""

from __future__ import annotations

from slh_mcp.capabilities import guarded_handler, list_capabilities
from slh_mcp.resources import register_resources


def register_capabilities(server):
    for capability in list_capabilities():
        if capability.handler is None:
            continue
        server.add_tool(
            guarded_handler(capability, capability.handler),
            name=capability.name,
            description=capability.description,
        )
    register_resources(server)
    return server
