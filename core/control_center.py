import state_manager
import json
import os
from datetime import datetime, timezone
from pathlib import Path

REGISTRY_FILE = Path("control_plane_registry.json")
RELEASE_EVIDENCE_ENV = "SLH_RELEASE_EVIDENCE_JSON"


EVIDENCE_STATUSES = {"PASS", "FAIL", "PENDING", "STALE", "UNKNOWN"}
EVIDENCE_SCOPES = {"read_only", "isolated", "runtime", "external"}
ACTION_POLICIES = {
    "collect_ci_evidence": {"safe": True, "mutation": False, "owner_required": False},
    "collect_new_user_join_e2e_evidence": {"safe": False, "mutation": True, "owner_required": True},
    "complete_bnb_opening_evidence": {"safe": False, "mutation": True, "owner_required": True},
}


def build_evidence(*, sha, domain, status, source, scope):
    """Create a validated, non-authoritative evidence record."""
    record = {
        "sha": str(sha or "unknown"),
        "domain": str(domain or "").strip(),
        "status": str(status or "UNKNOWN").upper(),
        "source": str(source or "").strip(),
        "scope": str(scope or "read_only").strip().lower(),
    }
    if not record["domain"]:
        raise ValueError("evidence domain is required")
    if not record["source"]:
        raise ValueError("evidence source is required")
    if record["status"] not in EVIDENCE_STATUSES:
        raise ValueError("invalid evidence status")
    if record["scope"] not in EVIDENCE_SCOPES:
        raise ValueError("invalid evidence scope")
    return record


def build_action(*, action, reason, safe, mutation=False, owner_required=False):
    """Create a descriptive action proposal; this function never executes it."""
    record = {
        "action": str(action or "").strip(),
        "reason": str(reason or "").strip(),
        "safe": bool(safe),
        "mutation": bool(mutation),
        "owner_required": bool(owner_required),
        "execution": "NOT_CONNECTED",
    }
    if not record["action"]:
        raise ValueError("action is required")
    if not record["reason"]:
        raise ValueError("action reason is required")
    if record["mutation"] and not record["owner_required"]:
        raise ValueError("mutating actions require owner approval")
    if record["safe"] and record["mutation"]:
        raise ValueError("safe actions must be non-mutating")
    return record


def classify_action(action, reason):
    """Classify a proposed action without executing it; unknown actions fail closed."""
    policy = ACTION_POLICIES.get(str(action or "").strip())
    if policy is None:
        return build_action(
            action=action,
            reason=reason,
            safe=False,
            mutation=True,
            owner_required=True,
        )
    return build_action(action=action, reason=reason, **policy)


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
        from core.bnb_gate import bnb_opening_evidence
        opening = bnb_opening_evidence() or {}
        result["bnb_opening_evidence"] = opening
        opening_status = str(opening.get("status", "")).upper()
        if opening_status == "READY_TO_OPEN":
            result["readiness"]["bnb_opening"] = "READY"
        elif opening_status == "BLOCKED":
            # BNB opening evidence is an advisory/read-only gate. A failed
            # live probe or pending empirical proof must not turn the whole
            # release state into BLOCKED; the actual settlement gate remains
            # independently fail-closed.
            result["readiness"]["bnb_opening"] = "PENDING"
        else:
            result["readiness"]["bnb_opening"] = "PENDING"
        if opening.get("warnings"):
            result["warnings"].extend(
                f"bnb_opening:{warning}" for warning in opening["warnings"]
            )
        if opening.get("blockers"):
            result["warnings"].extend(
                f"bnb_opening_blocker:{blocker}" for blocker in opening["blockers"]
            )
        if not opening.get("ready_to_open"):
            result["next_actions"].append("complete_bnb_opening_evidence")
    except Exception as exc:
        result["readiness"]["bnb_opening"] = "DEGRADED"
        result["warnings"].append("bnb_opening_evidence_unavailable")
        result["diagnostics"] = {"bnb_opening_error": type(exc).__name__}

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

    action_reasons = {
        "collect_ci_evidence": "CI runs are complete but release evidence is not yet correlated.",
        "collect_new_user_join_e2e_evidence": "New-user /join end-to-end evidence is still pending.",
        "complete_bnb_opening_evidence": "BNB opening evidence is incomplete and must remain fail-closed.",
    }
    for action in result["next_actions"]:
        proposal = classify_action(
            action,
            action_reasons.get(action, "Control Center reported an unresolved next action."),
        )
        if proposal["safe"] and not proposal["mutation"]:
            result["auto_actions"].append(proposal)
        else:
            result["owner_actions"].append(proposal)

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
