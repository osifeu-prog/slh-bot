# SLH MCP Service

Persistent MCP Control Plane service for SLH OS.

## Architecture boundary

slh-mcp is the MCP protocol layer. The web service remains the live owner of SLH user, agent, and mission state.

The MCP service reaches live state through the authenticated internal Control Plane bridge:

    slh-mcp
      -> HTTPS bridge
      -> web
      -> core.authority / Agent Registry / Runtime / Mission Lifecycle

It must not read the live user state directly from its own container filesystem.

## Local

Install:

    pip install -r slh_mcp/requirements.txt

Run:

    uvicorn slh_mcp.server:app --host 127.0.0.1 --port 8080 --workers 1

Health:

    GET /health

MCP endpoint:

    POST /mcp

## Required configuration

    SLH_MCP_BEARER_TOKEN
    SLH_MCP_PRINCIPAL_ID
    SLH_MCP_ALLOWED_HOSTS
    SLH_MCP_ALLOWED_ORIGINS
    SLH_CONTROL_PLANE_URL
    SLH_MCP_BRIDGE_TOKEN

SLH_MCP_BRIDGE_TOKEN must be configured in both web and slh-mcp.

There are no real secret values in this document.

## Capability model

Capabilities are declared explicitly in slh_mcp/capabilities.py.

The service does not scan Telegram handlers and does not expose arbitrary shell execution.

Current capability families include:

    system
    agents
    missions
    economy
    bots
    railway
    github

All privileged capabilities pass through the live Control Plane authority before execution.

## State boundaries

Existing user financial state remains outside the MCP write surface:

    state/db.json
    user Credits
    SLH/token balances
    staking positions
    historical user ledger
    token provenance

Agent Economy is isolated:

    state/agent_economy.json

It contains only agent-economy accounts, operations, and ledger entries.

Every agent-economy mutation requires a stable operation id and is idempotent.

The Agent Treasury may only be funded by record_revenue() with evidence; there is no arbitrary mint operation.

## Railway production

Create slh-mcp as an independent Railway service from repository root using:

    Dockerfile: slh_mcp/Dockerfile

Required persistent volume:

    Railway Volume -> /app/state

The volume is required before Agent Economy is used in production.

Run one worker initially. The agent ledger is file-backed and process-local locking is not sufficient for horizontal scaling.

Recommended host configuration:

    SLH_MCP_ALLOWED_HOSTS=<mcp-host>,<mcp-host>:*
    SLH_MCP_ALLOWED_ORIGINS=<allowed-origin>

Do not copy Telegram bot tokens into the slh-mcp service.

## Production smoke test

1. GET /health and require HTTP 200.
2. Connect an authenticated MCP client to /mcp.
3. Verify tool/resource discovery.
4. Call system.health, agents.list, missions.list.
5. Read economy.agent_balance for an agent visible to the authenticated principal.
6. Verify unauthenticated requests return 401.
7. Verify the live bridge is reached for authority/state reads.
8. Verify user financial regression is unchanged.