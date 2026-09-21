"""Agent MCP tools backed by the canonical SLH agent registry/runtime."""

from __future__ import annotations

from core.agent_registry import get_agent, list_agents
from core.authority import get_visible_agents
from core.runtime_service import execute_agent, status as runtime_status


_SENSITIVE_FIELDS = {"inbox", "history", "permissions", "owner_id"}
_MAX_COMMAND_LENGTH = 2000


def _resolve_principal(principal=None):
    if principal is not None:
        return principal
    from slh_mcp.auth import current_principal
    resolved = current_principal()
    if resolved is None:
        raise PermissionError("MCP authentication required")
    return resolved


def _public_agent(record: dict) -> dict:
    return {key: value for key, value in record.items() if key not in _SENSITIVE_FIELDS}


def agents_list(principal=None) -> list[dict]:
    principal = _resolve_principal(principal)
    visible = get_visible_agents(principal.subject, list_agents())
    return [_public_agent(item) for item in visible.values()]


def agents_get(principal, agent_id: str | None = None) -> dict:
    if agent_id is None:
        agent_id, principal = principal, None
    principal = _resolve_principal(principal)
    visible = get_visible_agents(principal.subject, list_agents())
    canonical_id, record = get_agent(str(agent_id))
    if record is None or canonical_id not in visible:
        raise KeyError(str(agent_id))
    return _public_agent(visible[canonical_id])


def agents_runtime_status(principal=None) -> dict:
    principal = _resolve_principal(principal)
    get_visible_agents(principal.subject, list_agents())
    snapshot = runtime_status()
    return {
        "state": snapshot.get("state"),
        "running": snapshot.get("running"),
        "boot_ok": snapshot.get("boot_ok"),
        "queue_size": snapshot.get("queue_size"),
        "thread_alive": snapshot.get("thread_alive"),
        "agent_count": len(snapshot.get("agents", [])),
    }


def agents_execute(principal, agent_id: str | None = None, command: str | None = None) -> dict:
    principal = _resolve_principal(principal)
    if agent_id is None or command is None:
        raise ValueError("agent_id and command are required")
    command = str(command).strip()
    if not command:
        raise ValueError("command cannot be empty")
    if len(command) > _MAX_COMMAND_LENGTH:
        raise ValueError("command exceeds maximum length")

    visible = get_visible_agents(principal.subject, list_agents())
    canonical_id, record = get_agent(str(agent_id))
    if record is None or canonical_id not in visible:
        raise KeyError(str(agent_id))
    return execute_agent(canonical_id, command, source="mcp")

def _tool_agents_list():
    return agents_list()


def _tool_agents_get(agent_id: str):
    return agents_get(None, agent_id)


def _tool_agents_runtime_status():
    return agents_runtime_status()


def _tool_agents_execute(agent_id: str, command: str):
    return agents_execute(None, agent_id, command)
