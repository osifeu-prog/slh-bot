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


def _token():
    token = os.getenv("RAILWAY_API_TOKEN") or os.getenv("RAILWAY_API_TOKEN_SLH")
    if not token:
        raise RailwayControlError(
            "RAILWAY_API_TOKEN is not configured. Add an account/workspace Railway API token."
        )
    return token


def graphql(query, variables=None):
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={
            "Authorization": "Bearer " + _token(),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise RailwayControlError(f"Railway API HTTP {exc.code}") from exc
    except Exception as exc:
        raise RailwayControlError(f"Railway API connection failed: {exc}") from exc

    if data.get("errors"):
        msg = data["errors"][0].get("message", "Railway API error")
        raise RailwayControlError(msg)
    return data.get("data", {})


def projects():
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
          ) { id }
        }
    """
    data = graphql(query, {
        "serviceId": service_id,
        "environmentId": environment_id,
        "commitSha": commit_sha,
    })
    return data["serviceInstanceDeployV2"]


def latest_github_commit(repo="osifeu-prog/slh-bot", branch="main"):
    url = f"https://api.github.com/repos/{repo}/commits/{branch}"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "SLH-Control-Plane"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode())["sha"]
    except Exception as exc:
        raise RailwayControlError(f"GitHub HEAD lookup failed: {exc}") from exc


def canonical_up():
    project_id = "fd30fefb-3d35-48a5-a7cb-e05337e8124c"
    service_id = "13d97581-0199-4f6a-80d1-885c9304ffc5"
    environment_id = "661caa13-83cb-4197-8825-943bebf96c5a"
    sha = latest_github_commit()
    deployment = deploy(service_id, environment_id, sha)
    return {
        "project": "endearing-amazement",
        "service": "web",
        "environment": "production",
        "commit": sha,
        "deployment_id": deployment.get("id"),
    }
