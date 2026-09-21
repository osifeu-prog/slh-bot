"""Authenticated client for the canonical SLH Control Plane bridge."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


_TIMEOUT = 15


def enabled() -> bool:
    return bool(
        os.getenv("SLH_CONTROL_PLANE_URL", "").strip()
        and os.getenv("SLH_MCP_BRIDGE_TOKEN", "").strip()
    )


def _base_url() -> str:
    value = os.getenv("SLH_CONTROL_PLANE_URL", "").strip().rstrip("/")
    if not value:
        raise RuntimeError("SLH_CONTROL_PLANE_URL not configured")
    return value


def _request(path: str, method: str = "GET", payload: dict | None = None) -> dict:
    token = os.getenv("SLH_MCP_BRIDGE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("SLH_MCP_BRIDGE_TOKEN not configured")

    body = None
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "SLH-MCP-Bridge/1",
    }
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        _base_url() + path,
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:300]
        except Exception:
            pass
        raise RuntimeError(f"CONTROL_PLANE_HTTP_{exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("CONTROL_PLANE_UNAVAILABLE") from exc

    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("CONTROL_PLANE_INVALID_JSON") from exc
    if not isinstance(data, dict):
        raise RuntimeError("CONTROL_PLANE_INVALID_RESPONSE")
    return data


def agents(_subject: str | None = None) -> dict:
    return _request("/internal/mcp/v1/agents")


def agent(agent_id: str, _subject: str | None = None) -> dict:
    return _request(f"/internal/mcp/v1/agents/{str(agent_id)}")


def runtime_status(_subject: str | None = None) -> dict:
    return _request("/internal/mcp/v1/runtime/status")


def agent_execute(agent_id: str, command: str, _subject: str | None = None) -> dict:
    return _request(
        f"/internal/mcp/v1/agents/{str(agent_id)}/execute",
        method="POST",
        payload={"command": str(command)},
    )


def missions(_subject: str | None = None) -> dict:
    return _request("/internal/mcp/v1/missions")


def mission(mission_id: str, _subject: str | None = None) -> dict:
    return _request(f"/internal/mcp/v1/missions/{str(mission_id)}")


def mission_complete(mission_id: str, _subject: str | None = None) -> dict:
    return _request(
        f"/internal/mcp/v1/missions/{str(mission_id)}/complete",
        method="POST",
        payload={},
    )
