"""Fixed, authenticated bot-to-MCP bridge for Exchange gate operations.

The Telegram handler enforces owner/private-chat authority. The remote bridge
accepts only status and close operations; it has no gate-open operation and
never returns Railway credentials or arbitrary variable contents.
"""
from __future__ import annotations

import os
import re

import requests


_SAFE_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,90}$")
_BASE_PATH = "/internal/telegram/exchange-gate"


class ExchangeGateBridgeError(RuntimeError):
    def __init__(self, code: str):
        self.code = str(code)
        super().__init__(self.code)


def _error_code(value) -> str:
    candidate = str(value or "")
    if _SAFE_CODE.fullmatch(candidate):
        return candidate
    return "MCP_BRIDGE_REQUEST_FAILED"


def _request(method: str, path: str) -> dict:
    base = os.getenv("SLH_MCP_URL", "").strip().rstrip("/")
    token = os.getenv("SLH_MCP_BRIDGE_TOKEN", "").strip()
    if not base or not token:
        raise ExchangeGateBridgeError("MCP_BRIDGE_NOT_CONFIGURED")

    try:
        response = requests.request(
            method,
            base + path,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            json={} if method == "POST" else None,
            timeout=15,
        )
    except requests.RequestException as exc:
        raise ExchangeGateBridgeError("MCP_BRIDGE_UNAVAILABLE") from exc

    try:
        data = response.json()
    except (ValueError, TypeError):
        data = {}

    if response.status_code == 401:
        raise ExchangeGateBridgeError("MCP_BRIDGE_AUTH_FAILED")
    if response.status_code == 403:
        raise ExchangeGateBridgeError("MCP_BRIDGE_ACCESS_DENIED")

    if response.status_code >= 400:
        error = data.get("error") if isinstance(data, dict) else None
        raise ExchangeGateBridgeError(_error_code(error))

    if not isinstance(data, dict):
        raise ExchangeGateBridgeError("MCP_BRIDGE_INVALID_RESPONSE")
    if data.get("status") == "ERROR":
        raise ExchangeGateBridgeError(_error_code(data.get("error")))
    return data


def exchange_gate_status() -> dict:
    """Read the Railway gate value through the authenticated Control Plane."""
    data = _request("GET", _BASE_PATH)
    if data.get("status") != "PASS":
        raise ExchangeGateBridgeError("MCP_BRIDGE_INVALID_RESPONSE")
    if data.get("configured") not in {"0", "1", "MISSING", "INVALID", "UNKNOWN"}:
        raise ExchangeGateBridgeError("MCP_BRIDGE_INVALID_RESPONSE")
    return data


def close_exchange_gate_via_mcp() -> dict:
    """Request the fixed close-only operation through MCP and Control Plane."""
    data = _request("POST", _BASE_PATH + "/close")
    if (
        data.get("status") != "DEPLOY_TRIGGERED"
        or data.get("configured") != "0"
        or not str(data.get("commit") or "")
        or not str(data.get("deployment_id") or "")
    ):
        raise ExchangeGateBridgeError("MCP_BRIDGE_INVALID_RESPONSE")
    return data
