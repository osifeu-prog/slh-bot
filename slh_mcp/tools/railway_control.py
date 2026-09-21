"""Governed Railway deployment control for MCP."""

from __future__ import annotations

import os
import re
import time

from core import railway_control
from core.authority import has_permission


_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_TERMINAL = {"SUCCESS", "FAILED", "CRASHED", "REMOVED", "REMOVING", "SLEEPING"}


def _principal(principal=None):
    if principal is not None:
        return principal
    from slh_mcp.auth import current_principal
    value = current_principal()
    if value is None:
        raise PermissionError("MCP authentication required")
    return value


def _targets() -> set[tuple[str, str, str]]:
    raw = os.getenv("SLH_MCP_DEPLOY_ALLOWLIST", "")
    result = set()
    for item in raw.split(","):
        parts = [part.strip() for part in item.split("|")]
        if len(parts) != 3 or not all(parts):
            continue
        result.add((parts[0], parts[1], parts[2]))
    return result


def _allowed(project_id: str, service_id: str, environment_id: str) -> bool:
    return (str(project_id), str(service_id), str(environment_id)) in _targets()


def _verify_terminal(deployment_id: str) -> dict:
    attempts = max(1, min(int(os.getenv("SLH_MCP_DEPLOY_POLL_ATTEMPTS", "30")), 120))
    delay = max(0.0, min(float(os.getenv("SLH_MCP_DEPLOY_POLL_SECONDS", "1")), 10.0))
    last = None
    for attempt in range(attempts):
        last = railway_control.deployment_status(deployment_id)
        status = str(last.get("status") or "").upper()
        if status in _TERMINAL:
            return last
        if attempt + 1 < attempts and delay:
            time.sleep(delay)
    return last or {"id": deployment_id, "status": "UNKNOWN"}


def railway_deploy(
    principal,
    project_id: str,
    service_id: str,
    environment_id: str,
    commit_sha: str,
) -> dict:
    principal = _principal(principal)
    project_id = str(project_id).strip()
    service_id = str(service_id).strip()
    environment_id = str(environment_id).strip()
    commit_sha = str(commit_sha).strip()

    if not has_permission(principal.subject, "agents.manage"):
        raise PermissionError("RAILWAY_DEPLOY_FORBIDDEN")
    if not _allowed(project_id, service_id, environment_id):
        raise PermissionError("RAILWAY_TARGET_NOT_ALLOWLISTED")
    if not _SHA_RE.fullmatch(commit_sha):
        raise ValueError("INVALID_COMMIT_SHA")

    deployment = railway_control.deploy(
        service_id=service_id,
        environment_id=environment_id,
        commit_sha=commit_sha,
    )
    deployment_id = str(deployment.get("id") or "").strip()
    if not deployment_id:
        raise RuntimeError("RAILWAY_DEPLOYMENT_ID_MISSING")

    status = _verify_terminal(deployment_id)
    return {
        "project_id": project_id,
        "service_id": service_id,
        "environment_id": environment_id,
        "commit_sha": commit_sha,
        "deployment": status,
        "terminal": str(status.get("status") or "").upper() in _TERMINAL,
    }


def _tool_railway_deploy(
    project_id: str,
    service_id: str,
    environment_id: str,
    commit_sha: str,
):
    return railway_deploy(
        None,
        project_id,
        service_id,
        environment_id,
        commit_sha,
    )
