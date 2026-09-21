"""Authenticated service-to-service bridge for SLH MCP."""

from __future__ import annotations

import hmac
import os


def require_mcp_bridge_token(request):
    expected = os.getenv("SLH_MCP_BRIDGE_TOKEN", "").strip()
    supplied = request.headers.get("X-SLH-MCP-Key", "").strip()

    if not expected:
        return ("config_error", 503)
    if not supplied or not hmac.compare_digest(supplied, expected):
        return ("forbidden", 403)
    return (None, None)


def mcp_principal(request):
    value = request.headers.get("X-SLH-MCP-Principal", "").strip()
    if not value or len(value) > 64:
        return None
    return value
