"""Explicit MCP capability catalog and binding metadata for SLH OS."""

from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

from mcp.server.mcpserver.exceptions import ToolError

from slh_mcp.auth import authorize, current_principal


@dataclass(frozen=True)
class Capability:
    name: str
    description: str
    permission: str
    mutating: bool
    handler: Callable[..., Any] | None = None


_READ_CAPABILITIES = (
    Capability("system.health", "Return safe MCP service health metadata.", "public.view", False),
    Capability("system.snapshot", "Return a safe SLH control-plane snapshot.", "public.view", False),
    Capability("agents.list", "List agents visible to the authenticated SLH principal.", "agents.view_self", False),
    Capability("agents.get", "Get one agent visible to the authenticated SLH principal.", "agents.view_self", False),
    Capability("agents.runtime_status", "Get canonical agent runtime status.", "agents.view_self", False),
    Capability("agents.execute", "Execute a validated command through the canonical agent runtime.", "agents.modify_self", True),
    Capability("missions.list", "List canonical SLH missions.", "public.view", False),
    Capability("economy.agent_balance", "Read isolated agent-economy balance.", "agents.view_self", False),
    Capability("economy.agent_ledger", "Read isolated agent-economy ledger.", "agents.view_self", False),
    Capability("economy.propose_transfer", "Validate an isolated agent-economy transfer without mutation.", "economy.mutate_self", False),
    Capability("railway.projects", "List Railway projects without environment values.", "exec.audit", False),
    Capability("railway.services", "List Railway services without environment values.", "exec.audit", False),
    Capability("railway.deployments", "List Railway deployment metadata without secrets.", "exec.audit", False),
    Capability("github.repositories", "List GitHub repository metadata.", "exec.audit", False),
    Capability("github.ci_status", "Read GitHub CI status for a commit.", "exec.audit", False),
    Capability("bots.registry", "Read the non-secret SLH bot ownership registry.", "exec.audit", False),
    Capability("bots.federation", "Cross-check registered bots against Railway service/deployment metadata.", "exec.audit", False),
)

_MUTATING_CAPABILITIES = (
    Capability("agents.create", "Create an SLH agent.", "agents.manage", True),
    Capability("agents.update", "Update an SLH agent.", "agents.manage", True),
    Capability("missions.create", "Create an SLH mission.", "agents.manage", True),
    Capability("missions.assign", "Assign an SLH mission.", "agents.manage", True),
    Capability("missions.complete", "Complete an SLH mission and record an agent reward.", "agents.manage", True),
    Capability("economy.commit_transfer", "Commit an isolated agent-economy transfer.", "economy.mutate_self", True),
    Capability("railway.deploy", "Deploy an allowlisted Railway target.", "agents.manage", True),
)

_CAPABILITIES = {item.name: item for item in (*_READ_CAPABILITIES, *_MUTATING_CAPABILITIES)}


def list_capabilities() -> list[Capability]:
    return list(_CAPABILITIES.values())


def get_capability(name: str) -> Capability:
    key = str(name).strip()
    if key not in _CAPABILITIES:
        raise KeyError(key)
    return _CAPABILITIES[key]


def bind_handler(name: str, handler: Callable[..., Any]) -> None:
    capability = get_capability(name)
    if capability.handler is not None:
        raise ValueError(f"Capability already bound: {name}")
    _CAPABILITIES[name] = Capability(
        name=capability.name,
        description=capability.description,
        permission=capability.permission,
        mutating=capability.mutating,
        handler=handler,
    )


def require_capability(name: str):
    capability = get_capability(name)
    principal = current_principal()
    if not authorize(principal, capability.permission):
        raise ToolError(f"Capability denied: {name}")
    return capability


def guarded_handler(capability: Capability, handler: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(handler)
    def guarded(*args, **kwargs):
        principal = current_principal()
        if not authorize(principal, capability.permission):
            raise ToolError(f"Capability denied: {capability.name}")
        return handler(*args, **kwargs)
    return guarded