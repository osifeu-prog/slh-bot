"""Read-only miner and ESP32 telemetry tools backed by the canonical Control Plane."""

from __future__ import annotations

from slh_mcp import control_plane_client
from slh_mcp.auth import authorize, current_principal


def _principal(principal=None):
    value = principal or current_principal()
    if value is None:
        raise PermissionError("MCP authentication required")
    if not authorize(value, "exec.audit"):
        raise PermissionError("MINER_STATUS_FORBIDDEN")
    return value


def miners_list(principal=None) -> dict:
    _principal(principal)
    return control_plane_client.miners()


def miner_status(device_id: str, principal=None) -> dict:
    _principal(principal)
    if not str(device_id or "").strip():
        raise ValueError("device_id required")
    return control_plane_client.miner(str(device_id).strip())


def _tool_miners_list():
    return miners_list()


def _tool_miner_status(device_id: str):
    return miner_status(device_id)
