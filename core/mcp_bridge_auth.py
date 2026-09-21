"""Authenticated service-to-service bridge authentication for SLH MCP."""

from __future__ import annotations

import hashlib
import hmac
import os


def _signature(secret: str, principal: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        principal.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def require_mcp_bridge_token(request):
    expected = os.getenv("SLH_MCP_BRIDGE_TOKEN", "").strip()
    supplied = request.headers.get("X-SLH-MCP-Key", "").strip()
    principal = request.headers.get("X-SLH-MCP-Principal", "").strip()
    signature = request.headers.get("X-SLH-MCP-Signature", "").strip()

    if not expected:
        return ("config_error", 503)
    if not supplied or not hmac.compare_digest(supplied, expected):
        return ("forbidden", 403)
    if not principal or len(principal) > 64:
        return ("principal_required", 400)

    expected_signature = _signature(expected, principal)
    if not signature or not hmac.compare_digest(signature, expected_signature):
        return ("forbidden", 403)

    return (None, None)


def mcp_principal(request):
    value = request.headers.get("X-SLH-MCP-Principal", "").strip()
    if not value or len(value) > 64:
        return None
    return value