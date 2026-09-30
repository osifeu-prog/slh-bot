import state_manager
import json
import os
from datetime import datetime, timezone
from pathlib import Path

REGISTRY_FILE = Path("control_plane_registry.json")
RELEASE_EVIDENCE_ENV = "SLH_RELEASE_EVIDENCE_JSON"


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


def _load_release_evidence():
    """Load optional externally collected, read-only release evidence."""
    raw = os.getenv(RELEASE_EVIDENCE_ENV, "").strip()
    if not raw:
        return {}
    try:
        evidence = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return evidence if isinstance(evidence, dict) else {}


def _correlate_release_evidence(result):
    """Apply only evidence explicitly supplied for the running commit."""
    evidence = _load_release_evidence()
    current_sha = get_deployment_state().get("commit", "unknown")
    result["release_evidence"] = {
        "source": "environment",
        "variable": RELEASE_EVIDENCE_ENV,
        "sha": evidence.get("sha", "unknown"),
        "matching_sha": bool(
            current_sha != "unknown"
            and evidence.get("sha")
            and evidence.get("sha") == current_sha
        ),
    }

    if not evidence:
        return

    evidence_sha = evidence.get("sha")
    if not evidence_sha or current_sha == "unknown":
        result["warnings"].append("release_evidence_sha_unavailable")
        return
    if evidence_sha != current_sha:
        result["warnings"].append("release_evidence_sha_mismatch")
        result["release_evidence"]["status"] = "STALE"
        return

    result["release_evidence"]["status"] = "MATCHED"

    ci = evidence.get("ci", {}) if isinstance(evidence.get("ci", {}), dict) else {}
    if ci.get("status") in {"PASS", "SUCCESS"}:
        result["readiness"]["ci"] = "READY"
        result["readiness"]["tests"] = "READY" if ci.get("tests_passed", True) else "DEGRADED"
        result["readiness"]["code"] = "READY" if ci.get("code_validated", True) else "DEGRADED"
        result["evidence"]["ci"] = "COLLECTED"

    deployment = evidence.get("deployment", {}) if isinstance(evidence.get("deployment", {}), dict) else {}
    deployment_source = deployment.get("source", "EXTERNAL_VERIFIED")
    if deployment.get("status") == "SUCCESS" and deployment_source != "github_handoff":
        result["readiness"]["deployment"] = "READY"
        result["evidence"]["deployment"] = "COLLECTED"
        result["deployment_verification"] = deployment_source


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
    snapshot["release_state"] = get_release_state()
    return snapshot


def get_release_state():
    """Read-only aggregate of release readiness and current operating gates."""
    result = {
        "overall": "DEGRADED",
        "readiness": {
            "code": "UNKNOWN",
            "tests": "UNKNOWN",
            "ci": "UNKNOWN",
            "deployment": "UNKNOWN",
            "runtime": "UNKNOWN",
            "alpha": "UNKNOWN",
            "e2e": "PENDING",
        },
        "evidence": {
            "system_check": "NOT_COLLECTED",
            "alpha_control_plane": "NOT_COLLECTED",
            "ci": "NOT_COLLECTED",
            "e2e": "PENDING",
            "deployment": "NOT_COLLECTED",
        },
        "current_state": {
            "alpha": "UNKNOWN",
            "bnb_settlement": "CLOSED",
            "ton_settlement": "CLOSED",
        },
        "ci": {"hosted": "UNKNOWN", "self_hosted": "UNKNOWN"},
        "blockers": [],
        "warnings": [],
        "next_actions": [],
        "auto_actions": [],
        "owner_actions": [],
        "scope": "read_only",
    }

    try:
        from core.system_check import run_system_checks
        checks = run_system_checks() or {}
        result["system_check"] = checks
        result["evidence"]["system_check"] = "COLLECTED"
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
        result["evidence"]["alpha_control_plane"] = "COLLECTED"
        alpha_status = str(alpha.get("status", "")).upper()
        result["readiness"]["alpha"] = (
            "READY" if alpha_status == "READY"
            else "BLOCKED" if alpha_status == "BLOCKED"
            else "DEGRADED"
        )
        alpha_runtime = alpha_state() or {}
        alpha_status = str(alpha_runtime.get("status", "")).upper()
        result["current_state"]["alpha"] = (
            "OPEN" if alpha_status == "OPEN"
            else "CLOSED" if alpha_status else "UNKNOWN"
        )
    except Exception as exc:
        result["readiness"]["alpha"] = "DEGRADED"
        result["warnings"].append("alpha_control_plane_unavailable")
        result["diagnostics"] = {"alpha_error": type(exc).__name__}

    try:
        from core.bnb_gate import bnb_readiness
        bnb = bnb_readiness() or {}
        result["bnb"] = bnb
        result["current_state"]["bnb_settlement"] = (
            "OPEN" if bnb.get("effective_open") is True else "CLOSED"
        )
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
    deployment_identity = get_deployment_state()
    result["deployment_identity"] = {
        "commit": deployment_identity.get("commit", "unknown"),
        "branch": deployment_identity.get("branch", "unknown"),
        "environment": deployment_identity.get("environment", "production"),
        "deployment_id": deployment_identity.get("deployment_id", "unknown"),
        "status": (
            "IDENTIFIED"
            if deployment_identity.get("commit") != "unknown"
            else "UNKNOWN"
        ),
    }
    result["deployment_verification"] = "UNVERIFIED"

    if result["infrastructure"].get("non_green_application_services", 0):
        result["warnings"].append("non_green_application_services")

    result["readiness"]["code"] = "UNKNOWN"
    result["readiness"]["tests"] = "UNKNOWN"
    result["readiness"]["ci"] = "UNKNOWN"
    result["evidence"]["ci"] = "NOT_COLLECTED"

    result["warnings"].extend([
        "code_evidence_not_collected",
        "test_evidence_not_collected",
        "ci_evidence_not_collected",
        "new_user_e2e_pending",
    ])
    result["next_actions"].extend([
        "collect_ci_evidence",
        "collect_new_user_join_e2e_evidence",
    ])

    _correlate_release_evidence(result)

    readiness_values = result["readiness"].values()
    if result["blockers"]:
        result["overall"] = "BLOCKED"
    elif any(value in {"UNKNOWN", "PENDING", "DEGRADED"} for value in readiness_values):
        result["overall"] = "DEGRADED"
    elif result["warnings"]:
        result["overall"] = "DEGRADED"
    else:
        result["overall"] = "GREEN"

    return result
