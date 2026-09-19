import state_manager
import json
import os
from datetime import datetime, timezone
from pathlib import Path

REGISTRY_FILE = Path("control_plane_registry.json")


def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _load_registry():
    return _load_json(REGISTRY_FILE, {
        "schema_version": "missing",
        "canonical": {},
        "railway_projects": [],
        "github_unmapped": [],
    })


def get_deployment_state():
    return {
        "commit": os.getenv("RAILWAY_GIT_COMMIT_SHA", os.getenv("COMMIT_SHA", "unknown")),
        "branch": os.getenv("RAILWAY_GIT_BRANCH", os.getenv("BRANCH", "unknown")),
        "environment": os.getenv("RAILWAY_ENVIRONMENT", "production"),
        "deployment_id": os.getenv("RAILWAY_DEPLOYMENT_ID", "unknown"),
    }


def get_infrastructure_snapshot():
    """Safe, non-secret Control Plane inventory."""
    registry = _load_registry()
    projects = registry.get("railway_projects", [])
    services = []

    for project in projects:
        for service in project.get("services", []):
            services.append({
                "project": project.get("name"),
                "project_id": project.get("id"),
                "service": service.get("name"),
                "service_id": service.get("id"),
                "repo": service.get("repo"),
                "branch": service.get("branch"),
                "status": service.get("status", "unknown"),
                "class": service.get("class", "unknown"),
            })

    non_green = [
        s for s in services
        if s.get("status") not in (None, "SUCCESS")
        and s.get("class") != "infrastructure"
    ]

    return {
        "schema_version": registry.get("schema_version", "missing"),
        "verified_date_utc": registry.get("verified_date_utc"),
        "canonical": registry.get("canonical", {}),
        "projects": len(projects),
        "services": len(services),
        "non_green_application_services": len(non_green),
        "non_green": non_green,
        "services_inventory": services,
        "github_unmapped": registry.get("github_unmapped", []),
    }


def get_system_snapshot():
    db = _load_json("state/db.json", {})
    ai = _load_json("state/ai_health.json", {})
    agents = state_manager.get_agents()
    users = db.get("users", {})

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system": {"status": "online"},
        "users": {"count": len(users)},
        "agents": {
            "count": len(agents),
            "active": len([a for a in agents.values() if a.get("state") == "active"]),
        },
        "ai": ai,
        "deployment": get_deployment_state(),
        "infrastructure": get_infrastructure_snapshot(),
    }
