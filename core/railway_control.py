"""Railway Control Plane API client.

Uses an account/workspace Railway API token from RAILWAY_API_TOKEN.
Never prints or returns the token.
"""

import json
import os
import urllib.request
import urllib.error

ENDPOINT = "https://backboard.railway.com/graphql/v2"


class RailwayControlError(RuntimeError):
    pass


def _auth_headers():
    project_token = os.getenv("RAILWAY_PROJECT_TOKEN") or os.getenv("RAILWAY_PROJECT_TOKEN_SLH")
    if project_token:
        return {            "Project-Access-Token": project_token,            "Content-Type": "application/json",            "Accept": "application/json",            "User-Agent": "SLH-Control-Plane/1.0",        }
    token = os.getenv("RAILWAY_API_TOKEN") or os.getenv("RAILWAY_API_TOKEN_SLH")
    if not token:
        raise RailwayControlError(
            "Railway token is not configured. Add RAILWAY_API_TOKEN for account/workspace control."
        )
    return {        "Authorization": "Bearer " + token,        "Content-Type": "application/json",        "Accept": "application/json",        "User-Agent": "SLH-Control-Plane/1.0",    }


def graphql(query, variables=None):
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers=_auth_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            body = ""
        detail = f": {body}" if body else ""
        raise RailwayControlError(f"Railway API HTTP {exc.code}{detail}") from exc
    except Exception as exc:
        raise RailwayControlError(f"Railway API connection failed: {exc}") from exc

    if data.get("errors"):
        msg = data["errors"][0].get("message", "Railway API error")
        raise RailwayControlError(msg)
    return data.get("data", {})


def projects():
    workspace_id = (        os.getenv("RAILWAY_WORKSPACE_ID")        or os.getenv("RAILWAY_WORKSPACE_ID_SLH")        or "e20e8242-57be-4ee3-9de8-c12684973570"    )
    if workspace_id:
        data = graphql("""
            query($id: String!) {
              workspace(workspaceId: $id) {
                id name
                projects { edges { node { id name } } }
              }
            }
        """, {"id": workspace_id})
        workspace = data.get("workspace") or {}
        return [x["node"] for x in workspace.get("projects", {}).get("edges", [])]

    data = graphql("""
        query {
          projects {
            edges {
              node { id name }
            }
          }
        }
    """)
    return [x["node"] for x in data.get("projects", {}).get("edges", [])]


def project(project_id):
    # The current workspace token is proven to list projects, but may not have
    # permission for the project resolver. Use the same authoritative listing
    # path first so inspect never reports an existing project as missing.
    for node in projects():
        if node.get("id") == project_id:
            return {"id": node.get("id"), "name": node.get("name")}

    data = graphql("""
        query($id: String!) {
          project(id: $id) {
            id name
            environments { edges { node { id name } } }
            services { edges { node { id name } } }
          }
        }
    """, {"id": project_id})
    return data.get("project")


def deploy(service_id, environment_id, commit_sha=None):
    query = """
        mutation($serviceId: String!, $environmentId: String!, $commitSha: String) {
          serviceInstanceDeployV2(
            serviceId: $serviceId
            environmentId: $environmentId
            commitSha: $commitSha
          )
        }
    """
    data = graphql(query, {
        "serviceId": service_id,
        "environmentId": environment_id,
        "commitSha": commit_sha,
    })
    deployment = data["serviceInstanceDeployV2"]
    return {"id": deployment}


def latest_github_commit(repo="osifeu-prog/slh-bot", branch="main"):
    url = f"https://api.github.com/repos/{repo}/commits/{branch}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "SLH-Control-Plane"}
    github_token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN_SLH")
    if github_token:
        headers["Authorization"] = "Bearer " + github_token
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode())["sha"]
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            body = ""
        hint = " (private repo likely requires GITHUB_TOKEN)" if exc.code == 404 and not github_token else ""
        raise RailwayControlError(f"GitHub HEAD lookup failed: HTTP {exc.code}{hint} {body}") from exc
    except Exception as exc:
        raise RailwayControlError(f"GitHub HEAD lookup failed: {exc}") from exc


def canonical_up(commit_sha=None):
    project_id = "fd30fefb-3d35-48a5-a7cb-e05337e812f4"
    service_id = "13d97581-0199-4f6a-80d1-885c9304ffc5"
    environment_id = "661caa13-83cb-4197-8825-943bebf96c5a"
    sha = str(commit_sha or "").strip() or latest_github_commit()
    deployment = deploy(service_id, environment_id, sha)
    return {
        "project": "endearing-amazement",
        "service": "web",
        "environment": "production",
        "commit": sha,
        "deployment_id": deployment.get("id"),
    }

def deployment_status(deployment_id):
    deployment_id = str(deployment_id).strip()
    if not deployment_id:
        raise RailwayControlError("INVALID_DEPLOYMENT_ID")
    data = graphql(
        """
        query($id: String!) {
          deployment(id: $id) {
            id
            status
            createdAt
            updatedAt
            projectId
            serviceId
            environmentId
          }
        }
        """,
        {"id": deployment_id},
    )
    deployment = data.get("deployment")
    if not isinstance(deployment, dict):
        raise RailwayControlError("DEPLOYMENT_NOT_FOUND")
    return {
        "id": deployment.get("id"),
        "status": deployment.get("status"),
        "created_at": deployment.get("createdAt"),
        "updated_at": deployment.get("updatedAt"),
        "project_id": deployment.get("projectId"),
        "service_id": deployment.get("serviceId"),
        "environment_id": deployment.get("environmentId"),
    }
