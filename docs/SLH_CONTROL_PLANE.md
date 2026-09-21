# SLH Control Plane

Canonical coordination layer for SLH OS development, runtime, federation, MCP, and release work.

## Current verified baseline — 2026-09-22

- **Git canonical branch:** `main` in `osifeu-prog/slh-bot`.
- **GitHub CI baseline:** the merged MCP Control Plane bridge passed `SLH CI`, `SLH Full Regression`, and the Railway handoff validation. The merged MQTT broker probe also passed `validate`, `full-regression`, and GitGuardian before merge.
- **MCP integration:** the standalone `slh-mcp` codebase is merged into `main`, including the authenticated Control Plane bridge.
- **Agent Economy:** isolated and idempotent; it does not rewrite user financial state.
- **Economic Read Model:** `core/economic_read_model.py` provides one normalized read model over user, revenue, and agent ledger events. It is a read model, not a second write ledger.
- **MQTT:** broker configuration/status is centralized and a read-only CONNECT/Disconnect probe is part of `main`.
- **Railway verification:** the current Railway connector session does not have sufficient viewer access to independently verify the live production deployment commit/configuration. Never infer live state from GitHub alone.

## Source-of-truth boundaries

- **GitHub:** versioned code, configuration, documentation, review, CI, and release history.
- **Railway:** runtime/deployment state and infrastructure topology.
- **SLH Bot state:** `state/db.json` is the current bot data plane; mutations go through the canonical state manager.
- **SLH API/Postgres:** separate API/data plane; authority for entities must be explicitly mapped.
- **AI sessions:** workers/clients of the Control Plane; they do not create competing canonical state.
- **Agent Economy:** `state/agent_economy.json` is a separate namespace for agent funds only.

## Runtime synchronization rules

1. Git `main` is the source of code truth; Railway is the source of live runtime truth.
2. Green GitHub CI is necessary but does not prove a production deployment is live.
3. A Railway deployment must reach terminal `SUCCESS` before it is reported as live.
4. `slh-mcp` is a separate service and must consume live Agents/Missions through the authenticated Control Plane bridge when running standalone.
5. The Telegram-facing `web` service remains the canonical SLH Control Plane runtime.
6. `slh-cloud-bot` is a non-polling secondary runtime in the latest registry snapshot: `RUN_BOT=0`, restart policy `NEVER`. Do not enable it as a Telegram poller without an explicit ownership/runtime decision verified in Railway.
7. No Telegram bot token belongs in `slh-mcp`.

## MCP contract

- **Transport:** Streamable HTTP over HTTPS.
- **Authentication:** bearer token at the MCP boundary plus canonical SLH authority checks.
- **Bridge:** `SLH_CONTROL_PLANE_URL` + `SLH_MCP_BRIDGE_TOKEN`.
- **Principal:** fixed by server-side configuration; clients cannot spoof it with a request header.
- **Capabilities:** explicitly registered; Telegram handlers are not auto-discovered.
- **Shell:** arbitrary shell execution is not an MCP capability.
- **Secrets:** tokens, keys, database URLs, and credentials are never returned by MCP tools/resources.

## Federation contract

The Control Plane can expose a non-secret federation view across registered bots and Railway targets. Legacy bots remain separate runtime/data planes until their identity, ownership, runtime, data, and capability contracts are explicitly verified.

Current registered bot ownership includes main, AIR, Claude, TON, and Tax Free. The registry records target ownership metadata, not secret values.

## Agent contract

Agents are durable SLH entities with registry identity, runtime state, mission state, capabilities, and agent-economy state.

Agent execution must follow:

```text
MCP / Telegram / Control client
        ↓
SLH authority
        ↓
canonical Agent Registry / Runtime
        ↓
audited action
```

## Economic contract

The system deliberately separates:

```text
User Credits / staking / existing financial ledger
                ≠
Agent Economy
                ≠
Economic Read Model
```

The Economic Read Model unifies events for observability. It does not become a new financial source of truth.

Agent monetary operations are:

```text
revenue evidence
      ↓
Agent Treasury
      ↓
proposal
      ↓
authority / policy
      ↓
idempotent commit
      ↓
Agent ledger
```

Existing user `credits`, `token_balance`, `staked`, staking positions, provenance records, and historical ledger rows are not migrated or rewritten by MCP.

## MQTT contract

- Configuration lives in `core/mqtt_config.py`.
- Device heartbeat listener lives in `core/mqtt_device_listener.py`.
- `mqtt.status` is configuration-only.
- `mqtt.probe` performs a read-only broker CONNECT/Disconnect and never publishes/subscribes or mutates device state.
- Device state continues through the existing canonical device state writer.

## AI handoff contract

Every AI session must be able to answer:

1. What is canonical?
2. What changed?
3. What is verified?
4. What remains open?
5. What must not be mutated?
6. What is the next exact action?

A completed investigation must not be restarted merely because a new session lacks context; read this document and the relevant incident/work files first.
