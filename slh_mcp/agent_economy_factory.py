"""Factory for the canonical Agent Economy backend."""

from __future__ import annotations

import os

from slh_mcp.agent_economy import AgentEconomyService
from slh_mcp.agent_economy_postgres import PostgresAgentEconomyService


def get_agent_economy_service(*, root="."):
    backend = str(os.getenv("SLH_AGENT_ECONOMY_BACKEND", "file")).strip().lower()
    if backend == "postgres":
        url = os.getenv("SLH_AGENT_ECONOMY_DATABASE_URL", "").strip()
        return PostgresAgentEconomyService(url)
    if backend == "file":
        return AgentEconomyService(root=root)
    raise ValueError("UNSUPPORTED_AGENT_ECONOMY_BACKEND")
