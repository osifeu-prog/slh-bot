"""Canonical project abstraction for the SLH Control Plane.

This layer composes existing runtime, agent, Railway and service registries.
It does not introduce a second state authority.
"""
from datetime import datetime, timezone

from core.agent_registry import list_agents
from core.runtime_service import status as runtime_status
from core.control_center import get_infrastructure_snapshot, get_deployment_state
import state_manager


def _owned_agents(owner_id=None):
    agents = list_agents()
    if owner_id is None:
        return agents
    owner_id = str(owner_id)
    return {
        aid: agent for aid, agent in agents.items()
        if str(agent.get("owner_id")) == owner_id
    }


def get_project_context(owner_id=None):
    """Return a safe, read-only project graph backed by existing authorities."""
    infra = get_infrastructure_snapshot()
    canonical = infra.get("canonical", {})
    agents = _owned_agents(owner_id)
    try:
        runtime = runtime_status()
    except Exception as exc:
        runtime = {"running": False, "error": type(exc).__name__}

    services = [
        s for s in infra.get("services_inventory", [])
        if s.get("class") != "infrastructure"
    ]

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "identity": {
            "name": "SLH",
            "canonical_repo": canonical.get("repo"),
            "railway_project": canonical.get("railway_project"),
            "railway_service": canonical.get("railway_service"),
        },
        "owner_id": str(owner_id) if owner_id is not None else None,
        "permissions": {
            "scope": "owner" if owner_id is None else "owner-scoped",
            "mutations": "not exposed by project context",
        },
        "ai_session": {
            "mode": "simple",
            "context_ready": True,
        },
        "agents": {
            "count": len(agents),
            "active": len([a for a in agents.values() if a.get("state") == "active"]),
            "items": agents,
        },
        "runtime": runtime,
        "services": services,
        "deployments": get_deployment_state(),
        "health": {
            "non_green_application_services": infra.get("non_green", []),
        },
        "journal": {
            "authority": "canonical persistent state/audit",
        },
    }
