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



def get_full_system_map():
    """Single read-only map used by the human-facing Control Plane."""
    from core.system_check import run_system_checks
    snapshot = get_system_snapshot()
    snapshot["verification"] = run_system_checks()
    return snapshot

def get_release_state():
    """Read-only aggregate of release readiness and current operating gates."""
    result = {
        "overall": "DEGRADED",
        "readiness": {"code": "UNKNOWN", "runtime": "UNKNOWN", "alpha": "UNKNOWN", "deployment": "UNKNOWN"},
        "current_state": {"alpha": "UNKNOWN", "bnb_settlement": "CLOSED", "ton_settlement": "CLOSED"},
        "ci": {"hosted": "UNKNOWN", "self_hosted": "UNKNOWN"},
        "blockers": [], "warnings": [], "auto_actions": [], "owner_actions": [],
        "scope": "read_only",
    }
    try:
        from core.system_check import run_system_checks
        checks = run_system_checks() or {}
        result["system_check"] = checks
        status = str(checks.get("status", "")).upper()
        if status in {"PASS", "READY", "GREEN"}:
            result["readiness"]["runtime"] = "READY"
        elif status in {"FAIL", "BLOCKED"}:
            result["readiness"]["runtime"] = "BLOCKED"
            result["blockers"].append("system_check")
        else:
            result["readiness"]["runtime"] = "DEGRADED"
            result["warnings"].append("system_check_status_unknown")
    except Exception as exc:
        result["readiness"]["runtime"] = "DEGRADED"
        result["warnings"].append("system_check_unavailable")
        result["diagnostics"] = {"system_check_error": type(exc).__name__}
    try:
        from core.alpha_control_plane import alpha_state, evaluate
        alpha = evaluate() or {}
        result["alpha"] = alpha
        alpha_status = str(alpha.get("status", "")).upper()
        result["readiness"]["alpha"] = "READY" if alpha_status == "READY" else "BLOCKED" if alpha_status == "BLOCKED" else "DEGRADED"
        alpha_runtime = alpha_state() or {}
        alpha_status = str(alpha_runtime.get("status", "")).upper()
        result["current_state"]["alpha"] = "OPEN" if alpha_status == "OPEN" else "CLOSED" if alpha_status else "UNKNOWN"
    except Exception as exc:
        result["readiness"]["alpha"] = "DEGRADED"
        result["warnings"].append("alpha_control_plane_unavailable")
        result["diagnostics"] = {"alpha_error": type(exc).__name__}
    try:
        from core.bnb_gate import bnb_readiness
        bnb = bnb_readiness() or {}
        result["bnb"] = bnb
        result["current_state"]["bnb_settlement"] = "OPEN" if bnb.get("effective_open") is True else "CLOSED"
    except Exception as exc:
        result["warnings"].append("bnb_gate_unavailable")
        result["diagnostics"] = {"bnb_error": type(exc).__name__}
    try:
        from core.ton_deposit_service import deposits_are_open
        ton_open = bool(deposits_are_open())
        result["current_state"]["ton_settlement"] = "OPEN" if ton_open else "CLOSED"
    except Exception as exc:
        result["warnings"].append("ton_gate_unavailable")
        result["diagnostics"] = {"ton_error": type(exc).__name__}
    result["infrastructure"] = get_infrastructure_snapshot()
    if result["infrastructure"].get("non_green_application_services", 0):
        result["warnings"].append("non_green_application_services")
    result["readiness"]["code"] = "BLOCKED" if result["blockers"] else "READY" if result["readiness"]["runtime"] == "READY" else "DEGRADED"
    result["readiness"]["deployment"] = "READY" if get_deployment_state().get("commit") != "unknown" else "UNKNOWN"
    result["overall"] = "BLOCKED" if result["blockers"] else "DEGRADED" if result["warnings"] else "GREEN"
    return result
