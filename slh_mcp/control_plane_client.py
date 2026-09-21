"""Authenticated HTTP client for the canonical SLH Control Plane."""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


class ControlPlaneBridgeError(RuntimeError):
    pass


def standalone_enabled() -> bool:
    return os.getenv("SLH_MCP_STANDALONE", "0").strip() == "1"


def configured() -> bool:
    return bool(
        os.getenv("SLH_CONTROL_PLANE_URL", "").strip()
        and os.getenv("SLH_MCP_BRIDGE_TOKEN", "").strip()
    )


def should_use_bridge() -> bool:
    return standalone_enabled() and configured()


def _base_url() -> str:
    value = os.getenv("SLH_CONTROL_PLANE_URL", "").strip().rstrip("/") + "/"
    if not value:
        raise ControlPlaneBridgeError("CONTROL_PLANE_URL_MISSING")
    return value


def _request(path: str, principal: str, *, method="GET", payload=None) -> dict:
    url = urljoin(_base_url(), path.lstrip("/"))
    headers = {
        "Accept": "application/json",
        "User-Agent": "SLH-MCP",
        "X-SLH-MCP-Bridge-Token": os.getenv("SLH_MCP_BRIDGE_TOKEN", ""),
        "X-SLH-MCP-Principal": str(principal),
    }
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, headers=headers, method=method)
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw or "{}")
    except HTTPError as exc:
        if exc.code in (401, 403, 404):
            raise ControlPlaneBridgeError(f"BRIDGE_HTTP_{exc.code}") from exc
        raise ControlPlaneBridgeError(f"BRIDGE_HTTP_{exc.code}") from exc
    except URLError as exc:
        raise ControlPlaneBridgeError("BRIDGE_UNAVAILABLE") from exc
    except json.JSONDecodeError as exc:
        raise ControlPlaneBridgeError("BRIDGE_INVALID_JSON") from exc


def get_agents(principal: str) -> list[dict]:
    return list(_request("/api/internal/mcp/agents", principal).get("agents", []))


def get_agent(principal: str, agent_id: str) -> dict:
    return dict(_request(f"/api/internal/mcp/agents/{agent_id}", principal).get("agent") or {})


def get_runtime(principal: str) -> dict:
    return dict(_request("/api/internal/mcp/runtime", principal))


def execute_agent(principal: str, agent_id: str, command: str) -> dict:
    return _request(
        f"/api/internal/mcp/agents/{agent_id}/execute",
        principal,
        method="POST",
        payload={"command": command},
    )


def get_missions(principal: str) -> list[dict]:
    return list(_request("/api/internal/mcp/missions", principal).get("missions", []))

def complete_mission(
    principal: str,
    mission_id: str,
    agent_id: str,
    result: dict | None = None,
) -> dict:
    payload = {"agent_id": str(agent_id)}
    if result is not None:
        payload["result"] = result
    return _request(
        f"/api/internal/mcp/missions/{mission_id}/complete",
        principal,
        method="POST",
        payload=payload,
    )
