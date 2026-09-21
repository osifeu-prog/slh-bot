"""Runtime configuration and readiness checks for SLH MCP."""

from __future__ import annotations

import os


REQUIRED = (
    "SLH_MCP_BEARER_TOKEN",
    "SLH_MCP_PRINCIPAL_ID",
    "SLH_MCP_ALLOWED_HOSTS",
    "SLH_CONTROL_PLANE_URL",
    "SLH_MCP_BRIDGE_TOKEN",
)


def readiness() -> dict:
    missing = [name for name in REQUIRED if not os.getenv(name, "").strip()]
    return {
        "ready": not missing,
        "missing": missing,
        "service": "SLH MCP",
    }
