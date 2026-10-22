"""Railway Control Plane API client.

Uses an account/workspace Railway API token from RAILWAY_API_TOKEN.
Never prints or returns the token.
"""

import json
import os
import urllib.request
import urllib.error
import time
from datetime import datetime, timezone

ENDPOINT = "https://backboard.railway.com/graphql/v2"


class RailwayControlError(RuntimeError):
    pass


def _auth_headers(*, prefer_account_token=False):
    account_token = os.getenv("RAILWAY_API_TOKEN") or os.getenv("RAILWAY_API_TOKEN_SLH")
    project_token = os.getenv("RAILWAY_PROJECT_TOKEN") or os.getenv("RAILWAY_PROJECT_TOKEN_SLH")

    # Cross-service Railway administration should prefer the account/workspace
    # token when one is configured; fall back to a project token scoped to the
    # target service's project. Never print or return either credential.
    token = account_token if prefer_account_token and account_token else None
    if token:
        return {
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SLH-Control-Plane/1.0",
        }
    if project_token:
        return {
            "Project-Access-Token": project_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SLH-Control-Plane/1.0",
        }
    if account_token:
        return {
            "Authorization": "Bearer " + account_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SLH-Control-Plane/1.0",
        }
    raise RailwayControlError(
        "RAILWAY_CONTROL_TOKEN_MISSING: configure RAILWAY_PROJECT_TOKEN for the target project "
        "or RAILWAY_API_TOKEN for account/workspace control."
    )


def safe_railway_error_code(exc):
    """Map Railway API exceptions to short, non-secret diagnostic codes."""
    message = str(exc or "").strip().lower()
    if "token_missing" in message or "token is not configured" in message:
        return "RAILWAY_CONTROL_TOKEN_MISSING"
    if "http 401" in message or "unauthorized" in message or "authentication" in message:
        return "RAILWAY_AUTHENTICATION_FAILED"
    if "http 403" in message or "forbidden" in message or "permission denied" in message or "not authorized" in message:
        return "RAILWAY_ACCESS_DENIED"
    if "http 404" in message or "not found" in message:
        return "RAILWAY_TARGET_NOT_FOUND"
    if "connection failed" in message or "timed out" in message or "timeout" in message:
        return "RAILWAY_API_UNREACHABLE"
    if "variable_read_failed" in message:
        return "RAILWAY_VARIABLE_READ_FAILED"
    if "variable_verify_failed" in message:
        return "RAILWAY_VARIABLE_VERIFY_FAILED"
    if "variable_update_rejected" in message:
        return "RAILWAY_VARIABLE_UPDATE_REJECTED"
    if "graphql" in message or "validation" in message or "cannot query field" in message:
        return "RAILWAY_GRAPHQL_SCHEMA_OR_REQUEST_ERROR"
    if "control_plane_bridge_token_missing" in message:
        return "CONTROL_PLANE_BRIDGE_TOKEN_MISSING"
    if "control_plane_bridge_unavailable" in message or "control_plane_unavailable" in message:
        return "CONTROL_PLANE_BRIDGE_UNAVAILABLE"
    if "exchange_control_auth_required" in message or "control_plane_http_401" in message:
        return "CONTROL_PLANE_BRIDGE_AUTH_FAILED"
    if "control_plane_http_404" in message or "control_plane_bridge_not_found" in message:
        return "CONTROL_PLANE_BRIDGE_NOT_FOUND"
    if "close_only_action_required" in message:
        return "CONTROL_PLANE_CLOSE_ONLY"
    if "exchange_gate_deploy_id_missing" in message:
        return "RAILWAY_DEPLOY_ID_MISSING"
    if "exchange_opening_proof_invalid" in message:
        return "EXCHANGE_OPENING_PROOF_INVALID"
    if "exchange_gate_not_closed" in message:
        return "EXCHANGE_GATE_NOT_CLOSED"
    if "exchange_gate_open_failed_rolled_back" in message:
        return "EXCHANGE_GATE_OPEN_FAILED_ROLLED_BACK"
    if "exchange_gate_open_compensation_failed" in message:
        return "EXCHANGE_GATE_OPEN_COMPENSATION_FAILED"
    if "exchange_gate_open_verify_failed" in message:
        return "EXCHANGE_GATE_OPEN_VERIFY_FAILED"
    if "exchange_gate_open_deploy_id_missing" in message:
        return "EXCHANGE_GATE_OPEN_DEPLOY_ID_MISSING"
    if "exchange_gate_open_not_verified" in message:
        return "EXCHANGE_GATE_OPEN_NOT_VERIFIED"
    return "RAILWAY_API_ERROR"


def graphql(query, variables=None, *, prefer_account_token=False):
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers=_auth_headers(prefer_account_token=prefer_account_token),
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
        """, {"id": workspace_id}, prefer_account_token=True)
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


def deploy(service_id, environment_id, commit_sha=None, *, prefer_account_token=False):
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
    }, prefer_account_token=prefer_account_token)
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

def deployment_status(deployment_id, *, prefer_account_token=False):
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
        prefer_account_token=prefer_account_token,
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


# Fixed production target for the owner-only Exchange close command.
# This function intentionally exposes a close operation only; it does not
# accept arbitrary project, service, variable, or value input from Telegram.
SLH_BOT_PROJECT_ID = "b33cb8d5-e82c-4a74-b94b-b52eb8c3d3db"
SLH_BOT_SERVICE_ID = "48b829d9-7bec-4d6c-ac25-025c77ce2794"
SLH_BOT_PRODUCTION_ENVIRONMENT_ID = "e82af387-87bb-40c9-b250-2e8a0b7fb41a"
SLH_EXCHANGE_GATE_VARIABLE = "SLH_EXCHANGE_PUBLIC_OPEN"


def exchange_gate_variable_status():
    """Return only the Exchange gate's value, never other service variables."""
    data = graphql(
        """
        query slhExchangeGateVariables(
          $projectId: String!,
          $environmentId: String!,
          $serviceId: String
        ) {
          variables(
            projectId: $projectId,
            environmentId: $environmentId,
            serviceId: $serviceId
          )
        }
        """,
        {
            "projectId": SLH_BOT_PROJECT_ID,
            "environmentId": SLH_BOT_PRODUCTION_ENVIRONMENT_ID,
            "serviceId": SLH_BOT_SERVICE_ID,
        },
        prefer_account_token=True,
    )
    values = data.get("variables")
    if not isinstance(values, dict):
        raise RailwayControlError("RAILWAY_VARIABLE_READ_FAILED")
    raw = values.get(SLH_EXCHANGE_GATE_VARIABLE)
    if raw is None:
        configured = "MISSING"
    else:
        value = str(raw).strip()
        configured = value if value in {"0", "1"} else "INVALID"
    return {
        "variable": SLH_EXCHANGE_GATE_VARIABLE,
        "configured": configured,
        "configured_open": configured == "1",
        "source": "railway_service_production",
    }


def close_exchange_gate():
    """Set the one Exchange gate to 0 and deploy the same running code revision.

    This is a one-way safety operation. It only changes the named service-level
    variable; it does not enumerate, return, replace, or expose other variables.
    """
    before = exchange_gate_variable_status()
    mutation = graphql(
        """
        mutation closeSLHExchangeGate($input: VariableUpsertInput!) {
          variableUpsert(input: $input)
        }
        """,
        {
            "input": {
                "projectId": SLH_BOT_PROJECT_ID,
                "environmentId": SLH_BOT_PRODUCTION_ENVIRONMENT_ID,
                "serviceId": SLH_BOT_SERVICE_ID,
                "name": SLH_EXCHANGE_GATE_VARIABLE,
                "value": "0",
                "skipDeploys": True,
            }
        },
        prefer_account_token=True,
    )
    if mutation.get("variableUpsert") is False:
        raise RailwayControlError("EXCHANGE_GATE_VARIABLE_UPDATE_REJECTED")

    after = exchange_gate_variable_status()
    if after.get("configured") != "0":
        raise RailwayControlError("EXCHANGE_GATE_VARIABLE_VERIFY_FAILED")

    commit_sha = str(os.getenv("RAILWAY_GIT_COMMIT_SHA") or "").strip()
    if len(commit_sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in commit_sha):
        commit_sha = latest_github_commit()

    deployment = deploy(
        SLH_BOT_SERVICE_ID,
        SLH_BOT_PRODUCTION_ENVIRONMENT_ID,
        commit_sha,
        prefer_account_token=True,
    )
    deployment_id = str((deployment or {}).get("id") or "")
    if not deployment_id:
        raise RailwayControlError("EXCHANGE_GATE_DEPLOY_ID_MISSING")

    return {
        "status": "DEPLOY_TRIGGERED",
        "previous": before.get("configured", "UNKNOWN"),
        "configured": after["configured"],
        "commit": commit_sha,
        "deployment_id": deployment_id,
        "service": "slh-cloud-bot",
        "environment": "production",
    }


# The Railway credential stays on the Control Plane service, never on the bot.
# This fixed endpoint supports status reads, explicit closes, and opening only
# with fresh canonical launch proof; no caller-provided URL/service/variable/value.
SLH_EXCHANGE_CONTROL_PLANE_URL = (
    "https://web-production-22f28.up.railway.app/api/internal/exchange-gate"
)


def _exchange_gate_bridge_request(method, payload=None, *, timeout_seconds=15):
    token = str(os.getenv("SLH_MCP_BRIDGE_TOKEN", "") or "").strip()
    if not token:
        raise RailwayControlError("CONTROL_PLANE_BRIDGE_TOKEN_MISSING")

    body = None
    headers = {
        "Accept": "application/json",
        "Authorization": "Bearer " + token,
        "User-Agent": "SLH-Exchange-Gate-Bridge/1",
    }
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        SLH_EXCHANGE_CONTROL_PLANE_URL,
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        code = ""
        try:
            body_json = json.loads(exc.read().decode("utf-8", errors="replace"))
            candidate = str(body_json.get("error") or "")
            if candidate and len(candidate) <= 96 and all(c.isupper() or c.isdigit() or c == "_" for c in candidate):
                code = candidate
        except Exception:
            pass
        if code:
            raise RailwayControlError(code) from exc
        if exc.code in {401, 403}:
            raise RailwayControlError("CONTROL_PLANE_BRIDGE_AUTH_FAILED") from exc
        if exc.code == 404:
            raise RailwayControlError("CONTROL_PLANE_BRIDGE_NOT_FOUND") from exc
        raise RailwayControlError("CONTROL_PLANE_BRIDGE_HTTP_ERROR") from exc
    except urllib.error.URLError as exc:
        raise RailwayControlError("CONTROL_PLANE_BRIDGE_UNAVAILABLE") from exc
    except Exception as exc:
        raise RailwayControlError("CONTROL_PLANE_BRIDGE_UNAVAILABLE") from exc

    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise RailwayControlError("CONTROL_PLANE_BRIDGE_INVALID_RESPONSE") from exc
    if not isinstance(data, dict):
        raise RailwayControlError("CONTROL_PLANE_BRIDGE_INVALID_RESPONSE")
    if data.get("ok") is not True:
        candidate = str(data.get("error") or "CONTROL_PLANE_BRIDGE_FAILED")
        if candidate and len(candidate) <= 96 and all(c.isupper() or c.isdigit() or c == "_" for c in candidate):
            raise RailwayControlError(candidate)
        raise RailwayControlError("CONTROL_PLANE_BRIDGE_FAILED")
    return data


def control_plane_exchange_gate_status(*, timeout_seconds=15):
    """Read only the single allowlisted Railway gate variable via the Control Plane.

    Callers that guard a user action may select a shorter fail-closed timeout.
    """
    data = _exchange_gate_bridge_request("GET", timeout_seconds=timeout_seconds)
    configured = str(data.get("configured") or "UNKNOWN")
    if configured not in {"0", "1", "MISSING", "INVALID"}:
        configured = "UNKNOWN"
    return {
        "variable": "SLH_EXCHANGE_PUBLIC_OPEN",
        "configured": configured,
        "configured_open": configured == "1",
        "source": "railway_control_plane_bridge",
    }


def request_exchange_gate_close():
    """Ask the Control Plane to set only SLH_EXCHANGE_PUBLIC_OPEN=0 and deploy."""
    data = _exchange_gate_bridge_request("POST", {"action": "close"})
    if data.get("configured") != "0" or data.get("status") != "DEPLOY_TRIGGERED":
        raise RailwayControlError("EXCHANGE_GATE_CLOSE_NOT_VERIFIED")
    return {
        "status": data["status"],
        "previous": data.get("previous", "UNKNOWN"),
        "configured": "0",
        "commit": str(data.get("commit") or ""),
        "deployment_id": str(data.get("deployment_id") or ""),
        "service": "slh-cloud-bot",
        "environment": "production",
    }



EXCHANGE_OPENING_PROOF_MAX_AGE_SECONDS = 120


def validate_exchange_opening_proof(proof, *, now=None):
    """Validate a fresh, launch-clean Exchange snapshot before any gate mutation."""
    if not isinstance(proof, dict):
        raise RailwayControlError("EXCHANGE_OPENING_PROOF_INVALID")

    try:
        checked_at = datetime.fromisoformat(
            str(proof.get("checked_at") or "").replace("Z", "+00:00")
        )
        current = now if now is not None else datetime.now(timezone.utc)
        if not isinstance(current, datetime) or current.tzinfo is None:
            raise ValueError("timezone-aware current time required")
        if checked_at.tzinfo is None:
            raise ValueError("timezone-aware proof timestamp required")
        age = (current.astimezone(timezone.utc) - checked_at.astimezone(timezone.utc)).total_seconds()
    except Exception as exc:
        raise RailwayControlError("EXCHANGE_OPENING_PROOF_INVALID") from exc

    if age < 0 or age > EXCHANGE_OPENING_PROOF_MAX_AGE_SECONDS:
        raise RailwayControlError("EXCHANGE_OPENING_PROOF_INVALID")

    if (
        proof.get("status") != "PASS"
        or proof.get("public_gate") != "CLOSED"
        or proof.get("verdict") != "READY_TO_OPEN"
        or proof.get("public_ready") is not True
        or proof.get("order_book_integrity") is not True
        or proof.get("trade_integrity") is not True
        or proof.get("money_invariants") is not True
    ):
        raise RailwayControlError("EXCHANGE_OPENING_PROOF_INVALID")

    for field in ("open_orders", "test_seed_open", "test_seed_trades"):
        value = proof.get(field)
        if type(value) is not int or value != 0:
            raise RailwayControlError("EXCHANGE_OPENING_PROOF_INVALID")

    return {
        "status": "PASS",
        "checked_at": checked_at.astimezone(timezone.utc).isoformat(),
        "public_gate": "CLOSED",
        "verdict": "READY_TO_OPEN",
        "public_ready": True,
        "order_book_integrity": True,
        "trade_integrity": True,
        "money_invariants": True,
        "open_orders": 0,
        "test_seed_open": 0,
        "test_seed_trades": 0,
    }


def _set_exchange_gate_variable(value):
    """Set only the allowlisted Exchange gate variable; never exposes other variables."""
    if value not in {"0", "1"}:
        raise RailwayControlError("EXCHANGE_GATE_VALUE_INVALID")
    mutation = graphql(
        """
        mutation setSLHExchangeGate($input: VariableUpsertInput!) {
          variableUpsert(input: $input)
        }
        """,
        {
            "input": {
                "projectId": SLH_BOT_PROJECT_ID,
                "environmentId": SLH_BOT_PRODUCTION_ENVIRONMENT_ID,
                "serviceId": SLH_BOT_SERVICE_ID,
                "name": SLH_EXCHANGE_GATE_VARIABLE,
                "value": value,
                "skipDeploys": True,
            }
        },
        prefer_account_token=True,
    )
    if mutation.get("variableUpsert") is False:
        raise RailwayControlError("RAILWAY_VARIABLE_UPDATE_REJECTED")


def _exchange_gate_commit_sha():
    commit_sha = str(os.getenv("RAILWAY_GIT_COMMIT_SHA") or "").strip()
    if len(commit_sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in commit_sha):
        commit_sha = latest_github_commit()
    if len(str(commit_sha or "")) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in str(commit_sha)):
        raise RailwayControlError("EXCHANGE_GATE_OPEN_COMMIT_INVALID")
    return str(commit_sha)


EXCHANGE_GATE_DEPLOY_WAIT_SECONDS = 120
EXCHANGE_GATE_DEPLOY_POLL_SECONDS = 2


def _wait_for_deployment_success(deployment_id):
    """Wait for a terminal successful deployment or raise a safe status code."""
    deployment_id = str(deployment_id or "").strip()
    if not deployment_id:
        raise RailwayControlError("EXCHANGE_GATE_OPEN_DEPLOY_ID_MISSING")

    deadline = time.monotonic() + EXCHANGE_GATE_DEPLOY_WAIT_SECONDS
    in_progress = {"WAITING", "QUEUED", "INITIALIZING", "BUILDING", "DEPLOYING"}
    while True:
        state = deployment_status(deployment_id, prefer_account_token=True)
        status = str(state.get("status") or "").strip().upper()
        if status == "SUCCESS":
            return state
        if status not in in_progress:
            raise RailwayControlError("EXCHANGE_GATE_OPEN_DEPLOY_FAILED")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RailwayControlError("EXCHANGE_GATE_OPEN_DEPLOY_TIMEOUT")
        time.sleep(min(EXCHANGE_GATE_DEPLOY_POLL_SECONDS, remaining))


def _compensate_exchange_gate_closed(commit_sha):
    """Fail closed and verify the reconciliation deployment reached SUCCESS."""
    _set_exchange_gate_variable("0")
    restored = exchange_gate_variable_status()
    if restored.get("configured") != "0":
        raise RailwayControlError("EXCHANGE_GATE_OPEN_COMPENSATION_FAILED")
    deployment = deploy(
        SLH_BOT_SERVICE_ID,
        SLH_BOT_PRODUCTION_ENVIRONMENT_ID,
        commit_sha,
        prefer_account_token=True,
    )
    deployment_id = str((deployment or {}).get("id") or "")
    if not deployment_id:
        raise RailwayControlError("EXCHANGE_GATE_OPEN_COMPENSATION_FAILED")
    _wait_for_deployment_success(deployment_id)
    return True


def open_exchange_gate(proof):
    """Open only the fixed internal Exchange gate after validating fresh launch evidence."""
    validated = validate_exchange_opening_proof(proof)
    before = exchange_gate_variable_status()
    if before.get("configured") != "0":
        raise RailwayControlError("EXCHANGE_GATE_NOT_CLOSED")

    # Resolve the exact revision before mutating configuration so a failed
    # commit lookup cannot leave an open value waiting for a later deployment.
    commit_sha = _exchange_gate_commit_sha()

    try:
        _set_exchange_gate_variable("1")
        after = exchange_gate_variable_status()
        if after.get("configured") != "1":
            raise RailwayControlError("EXCHANGE_GATE_OPEN_VERIFY_FAILED")

        deployment = deploy(
            SLH_BOT_SERVICE_ID,
            SLH_BOT_PRODUCTION_ENVIRONMENT_ID,
            commit_sha,
            prefer_account_token=True,
        )
        deployment_id = str((deployment or {}).get("id") or "")
        if not deployment_id:
            raise RailwayControlError("EXCHANGE_GATE_OPEN_DEPLOY_ID_MISSING")
        _wait_for_deployment_success(deployment_id)
    except Exception as exc:
        try:
            compensated = _compensate_exchange_gate_closed(commit_sha)
        except Exception as rollback_exc:
            raise RailwayControlError("EXCHANGE_GATE_OPEN_COMPENSATION_FAILED") from rollback_exc
        if not compensated:
            raise RailwayControlError("EXCHANGE_GATE_OPEN_COMPENSATION_FAILED") from exc
        raise RailwayControlError("EXCHANGE_GATE_OPEN_FAILED_ROLLED_BACK") from exc

    return {
        "status": "DEPLOYMENT_SUCCESS",
        "previous": before.get("configured", "UNKNOWN"),
        "configured": after["configured"],
        "commit": commit_sha,
        "deployment_id": deployment_id,
        "proof_checked_at": validated["checked_at"],
        "service": "slh-cloud-bot",
        "environment": "production",
    }


def request_exchange_gate_open(proof):
    """Request opening through the authenticated Control Plane with fresh proof."""
    validated = validate_exchange_opening_proof(proof)
    data = _exchange_gate_bridge_request(
        "POST",
        {"action": "open", "proof": validated},
        timeout_seconds=260,
    )
    if data.get("configured") != "1" or data.get("status") != "DEPLOYMENT_SUCCESS":
        raise RailwayControlError("EXCHANGE_GATE_OPEN_NOT_VERIFIED")
    return {
        "status": data["status"],
        "previous": data.get("previous", "UNKNOWN"),
        "configured": "1",
        "commit": str(data.get("commit") or ""),
        "deployment_id": str(data.get("deployment_id") or ""),
        "proof_checked_at": validated["checked_at"],
        "service": "slh-cloud-bot",
        "environment": "production",
    }
