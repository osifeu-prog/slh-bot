"""Read-only Railway and GitHub adapters for MCP."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from core.railway_control import RailwayControlError, graphql, projects


def railway_projects(principal=None) -> list[dict]:
    _require_principal(principal)
    return [
        {"id": str(item.get("id")), "name": str(item.get("name"))}
        for item in projects()
    ]


def railway_services(principal, project_id: str) -> list[dict]:
    _require_principal(principal)
    project = _safe_project(project_id)
    if not project:
        raise KeyError(str(project_id))
    rows = project.get("services", {}).get("edges", [])
    result = []
    for row in rows:
        node = row.get("node") if isinstance(row, dict) else None
        if not isinstance(node, dict):
            continue
        instances = node.get("serviceInstances", {}).get("edges", [])
        latest = None
        if instances and isinstance(instances[0], dict):
            instance = instances[0].get("node") or {}
            latest = instance.get("latestDeployment")
        result.append({
            "id": str(node.get("id")),
            "name": str(node.get("name")),
            "latest_deployment": {
                "id": latest.get("id"),
                "status": latest.get("status"),
                "created_at": latest.get("createdAt"),
            } if isinstance(latest, dict) else None,
        })
    return result


def railway_deployments(principal, project_id: str, service_id: str | None = None) -> list[dict]:
    _require_principal(principal)
    project = _safe_project(project_id)
    if not project:
        raise KeyError(str(project_id))
    rows = project.get("services", {}).get("edges", [])
    services = []
    for row in rows:
        node = row.get("node") if isinstance(row, dict) else None
        if isinstance(node, dict):
            if service_id and str(node.get("id")) != str(service_id):
                continue
            services.append(node)
    deployments = []
    for node in services:
        instances = node.get("serviceInstances", {}).get("edges", [])
        for instance_row in instances:
            instance = instance_row.get("node") if isinstance(instance_row, dict) else None
            latest = instance.get("latestDeployment") if isinstance(instance, dict) else None
            if isinstance(latest, dict):
                deployments.append({
                    "service_id": str(node.get("id")),
                    "service_name": str(node.get("name")),
                    "id": latest.get("id"),
                    "status": latest.get("status"),
                    "created_at": latest.get("createdAt"),
                })
    return deployments


def github_repositories(principal=None) -> list[dict]:
    _require_principal(principal)
    configured = [
        item.strip()
        for item in os.getenv("SLH_GITHUB_REPOSITORIES", "osifeu-prog/slh-bot").split(",")
        if item.strip()
    ]
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN_SLH")
    rows = []
    for repo in configured:
        url = f"https://api.github.com/repos/{repo}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "SLH-MCP",
        }
        if token:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403, 404):
                rows.append({"name": repo, "status": "unavailable"})
                continue
            raise
        rows.append({
            "name": data.get("full_name", repo),
            "default_branch": data.get("default_branch"),
            "private": bool(data.get("private")),
        })
    return rows


def github_ci_status(principal, repo: str, commit_sha: str) -> dict:
    _require_principal(principal)
    repo = str(repo).strip()
    commit_sha = str(commit_sha).strip()
    if not repo or len(commit_sha) != 40:
        raise ValueError("INVALID_GITHUB_QUERY")

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN_SLH")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "SLH-MCP",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    url = f"https://api.github.com/repos/{repo}/commits/{commit_sha}/check-runs"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GITHUB_CHECKS_HTTP_{exc.code}") from exc

    return {
        "repo": repo,
        "commit": commit_sha,
        "total": int(data.get("total_count", 0)),
        "checks": [
            {
                "name": item.get("name"),
                "status": item.get("status"),
                "conclusion": item.get("conclusion"),
            }
            for item in data.get("check_runs", [])
        ],
    }


def _require_principal(principal):
    if principal is not None:
        return principal
    from slh_mcp.auth import current_principal
    value = current_principal()
    if value is None:
        raise PermissionError("MCP authentication required")
    return value


def _safe_project(project_id: str) -> dict | None:
    try:
        data = graphql(
            """
            query($id: String!) {
              project(id: $id) {
                id name
                services {
                  edges {
                    node {
                      id
                      name
                      serviceInstances {
                        edges {
                          node {
                            latestDeployment {
                              id
                              status
                              createdAt
                              meta
                            }
                          }
                        }
                      }
                    }
                  }
                }
                environments { edges { node { id name } } }
              }
            }
            """,
            {"id": str(project_id)},
        )
        return data.get("project")
    except RailwayControlError:
        return None


def _tool_railway_projects():
    return railway_projects(None)


def _tool_railway_services(project_id: str):
    return railway_services(None, project_id)


def _tool_railway_deployments(project_id: str, service_id: str | None = None):
    return railway_deployments(None, project_id, service_id)


def _tool_github_repositories():
    return github_repositories(None)


def _tool_github_ci_status(repo: str, commit_sha: str):
    return github_ci_status(None, repo, commit_sha)