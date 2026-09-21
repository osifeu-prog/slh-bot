# SLH MCP Service

Persistent MCP Control Plane service for SLH OS.

## Local

Install:

    pip install -r slh_mcp/requirements.txt

Run:

    uvicorn slh_mcp.server:app --host 127.0.0.1 --port 8080

Health:

    GET /health

MCP endpoint:

    POST /mcp

## Required configuration

    SLH_MCP_BEARER_TOKEN
    SLH_MCP_PRINCIPAL_ID
    SLH_MCP_ALLOWED_HOSTS
    SLH_MCP_ALLOWED_ORIGINS

Railway deployment control additionally requires:

    SLH_MCP_DEPLOY_ALLOWLIST

Format:

    project_id|service_id|environment_id[,project_id|service_id|environment_id...]

There are no real secret values in this document.

## Design rules

The MCP service is a protocol layer over the canonical SLH Control Plane.
It does not replace Telegram handlers, does not maintain a second authority model, and does not write directly to state/db.json.
Agent-economy state is isolated in state/agent_economy.json.
Existing user Credits, SLH/token balances, staking positions, provenance, and historical user ledger records are outside the MCP write surface.
Arbitrary shell execution is not an MCP capability.