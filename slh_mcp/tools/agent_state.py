"""Read-only agent state diagnostics for Control Plane federation."""

from __future__ import annotations

from core.agent_state_store import AgentStateStore
from core.agent_registry import list_agents
from core.authority import get_visible_agents


def _principal(principal=None):
    if principal is not None:
        return principal
    from slh_mcp.auth import current_principal
    value = current_principal()
    if value is None:
        raise PermissionError("MCP authentication required")
    return value


def agents_consistency(principal=None) -> dict:
    principal = _principal(principal)
    visible = get_visible_agents(principal.subject, list_agents())
    audit = AgentStateStore().audit()
    records = []
    for agent_id, agent in visible.items():
        created = str(agent.get("created") or "")
        records.append({
            "agent_id": str(agent_id),
            "display_number": 0,
            "name": agent.get("name"),
            "state": agent.get("state"),
            "owner_id": agent.get("owner_id") if str(principal.role) == "OWNER" else None,
            "created": created,
        })
    by_owner = {}
    for row in sorted(records, key=lambda x: (str(x.get("owner_id") or ""), str(x.get("created") or ""), x["agent_id"])):
        key = str(row.get("owner_id") or principal.subject)
        by_owner[key] = by_owner.get(key, 0) + 1
        row["display_number"] = by_owner[key]
    return {
        "canonical_source": "state/db.json",
        "snapshot": "state/agents.json",
        "db_count": audit.get("db_count", 0),
        "snapshot_count": audit.get("snapshot_count", 0),
        "state_drift": audit.get("issues", []),
        "canonical_visible_agents": records,
        "ok": bool(audit.get("ok")) and audit.get("db_count") == audit.get("snapshot_count"),
    }


def _tool_agents_consistency():
    return agents_consistency()
