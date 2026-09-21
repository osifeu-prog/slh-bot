"""Federated read model for the SLH bot fleet."""

from __future__ import annotations

from core.telegram_token_registry import list_bots

from slh_mcp.tools.integrations import railway_deployments, railway_projects


def bots_federation(principal=None) -> list[dict]:
    if principal is None:
        from slh_mcp.auth import current_principal
        principal = current_principal()
    if principal is None:
        raise PermissionError("MCP authentication required")

    projects = {row["id"]: row for row in railway_projects(principal)}
    result = []

    for bot in list_bots():
        targets = []
        for target in bot.get("targets", []):
            project_id = str(target.get("project_id"))
            service_id = str(target.get("service_id"))
            project = projects.get(project_id)
            deployment_rows = []
            try:
                deployment_rows = railway_deployments(
                    principal,
                    project_id,
                    service_id,
                )
            except Exception:
                deployment_rows = []

            latest = deployment_rows[0] if deployment_rows else None
            if not project:
                state = "PROJECT_MISSING"
            elif latest is None:
                state = "SERVICE_OR_DEPLOYMENT_UNKNOWN"
            elif latest.get("status") == "SUCCESS":
                state = "READY"
            else:
                state = "ATTENTION"

            targets.append({
                "project": target.get("project"),
                "project_id": project_id,
                "service": target.get("service"),
                "service_id": service_id,
                "environment": target.get("environment"),
                "variable": target.get("variable"),
                "project_found": bool(project),
                "latest_deployment": latest,
                "state": state,
            })

        result.append({
            "alias": bot.get("alias"),
            "username": bot.get("username"),
            "label": bot.get("label"),
            "targets": targets,
        })

    return result


def _tool_bots_federation():
    return bots_federation()
