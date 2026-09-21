"""Read/write client for the canonical SLH Control Plane bridge."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


class ControlPlaneBridgeError(RuntimeError):
    pass


def _request(path: str, *, method="GET", payload=None):
    base = os.getenv("SLH_CONTROL_PLANE_URL", "").rstrip("/")
    token = os.getenv("SLH_MCP_BRIDGE_TOKEN", "").strip()
    principal = os.getenv("SLH_MCP_PRINCIPAL_ID", "").strip()
    if not base or not token or not principal:
        raise ControlPlaneBridgeError("MCP_BRIDGE_NOT_CONFIGURED")

    body = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "SLH-MCP",
        "X-SLH-MCP-Key": token,
        "X-SLH-MCP-Principal": principal,
    }
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        base + path,
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ControlPlaneBridgeError(f"CONTROL_PLANE_HTTP_{exc.code}") from exc
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise ControlPlaneBridgeError("CONTROL_PLANE_UNAVAILABLE") from exc


def agents():
    return _request("/api/internal/mcp/agents")


def agent(agent_id: str):
    return _request("/api/internal/mcp/agents/" + str(agent_id))


def agent_execute(agent_id: str, command: str):
    return _request(
        "/api/internal/mcp/agents/" + str(agent_id) + "/execute",
        method="POST",
        payload={"command": command},
    )


def missions():
    return _request("/api/internal/mcp/missions")


def mission(mission_id: str):
    return _request("/api/internal/mcp/missions/" + str(mission_id))


def mission_complete(mission_id: str):
    return _request(
        "/api/internal/mcp/missions/" + str(mission_id) + "/complete",
        method="POST",
    )

def authorize(permission: str) -> bool:
    result = _request(
        "/api/internal/mcp/authorize",
        method="POST",
        payload={"permission": str(permission)},
    )
    return bool(result.get("authorized"))


def runtime_status():
    return _request("/api/internal/mcp/runtime-status")
