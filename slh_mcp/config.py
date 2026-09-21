"""Runtime configuration and readiness checks for SLH MCP."""

from __future__ import annotations

import os


BASE_REQUIRED = (
    "SLH_MCP_BEARER_TOKEN",
    "SLH_MCP_PRINCIPAL_ID",
    "SLH_MCP_ALLOWED_HOSTS",
)


def standalone() -> bool:
    return os.getenv("SLH_MCP_STANDALONE", "0").strip() == "1"


def required_variables() -> tuple[str, ...]:
    if standalone():
        return BASE_REQUIRED + (
            "SLH_CONTROL_PLANE_URL",
            "SLH_MCP_BRIDGE_TOKEN",
        )
    return BASE_REQUIRED


def readiness() -> dict:
    missing = [
        name
        for name in required_variables()
        if not os.getenv(name, "").strip()
    ]
    return {
        "ready": not missing,
        "missing": missing,
        "mode": "standalone" if standalone() else "embedded",
        "service": "SLH MCP",
    }
