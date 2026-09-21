# SLH Control Plane

Canonical coordination layer for SLH OS development, runtime, and release work.

## Current verified baseline — 2026-09-22

- **Git canonical main:** `3e2ca331e2aae4cccd8e7125713069cefa32a439`.
- **GitHub CI for that commit:** `SLH CI`, `SLH Full Regression`, and `Validate and hand off to Railway` are green.
- **MCP integration:** the standalone MCP → canonical web Control Plane bridge is merged into `main`.
- **Agent Economy:** isolated agent ledger exists separately from user financial state.
- **Economic Read Model:** `core/economic_read_model.py` provides one normalized read model across user, revenue, and agent ledger events; it is not a replacement write ledger.
- **MQTT:** configuration/status is centralized; a read-only broker probe is implemented on the pending MQTT change set and must be green/merged before being treated as part of main.
- **Railway verification:** the current Railway connector session does not have sufficient viewer access to independently verify the live deployment commit/configuration. Never infer live state from GitHub alone.

## Source-of-truth boundaries

- **GitHub**: versioned code, configuration, documentation, review and release history.
- **Railway**: runtime/deployment state and infrastructure topology.
- **SLH Bot state**: `state/db.json` is the current bot data plane; writes must go through the canonical state manager.
- **SLH API/Postgres**: separate API/data plane; must be mapped before declaring it authoritative for any entity.
- **AI sessions**: workers/clients of the Control Plane. They do not create competing canonical state.

## Runtime synchronization rules

- Git `main` is the code baseline; Railway determines what is actually live.
- A successful GitHub check is not proof of a production deployment.
- A Railway `SUCCESS` deployment is required before claiming a service is live.
- `slh-mcp` is a separate service and must use the authenticated Control Plane bridge for live Agents/Missions; it must not read another service's local `state/db.json`.
- The public/Telegram-facing `web` service remains the canonical Control Plane runtime.
- `slh-cloud-bot` remains a non-polling secondary runtime in the latest repository registry snapshot (`RUN_BOT=0`, restart policy `NEVER`). Do not enable it as a Telegram poller until its ownership/runtime role is explicitly changed and verified in Railway.
- No Telegram bot token belongs in the MCP service.

## Current integration boundaries

- The main bot, Mini App, and `slh-api` remain distinct runtime/data planes.
- MCP is the protocol-facing layer over the Control Plane; Telegram handlers are presentation/input surfaces.
- Legacy bots remain federated adapters until their identity, runtime, data, and capability contracts are verified.
- User financial state is not migrated or rewritten by MCP.
- Agent economy uses its own namespace and idempotent operations.

## Source-of-truth boundaries

- **GitHub**: versioned code, configuration, documentation, review and release history.
- **Railway**: runtime/deployment state and infrastructure topology.
- **SLH Bot state**: `state/db.json` is the current bot data plane; writes must go through the canonical state manager.
- **SLH API/Postgres**: separate API/data plane; must be mapped before declaring it authoritative for any entity.
- **AI sessions**: workers/clients of the Control Plane. They do not create competing canonical state.

## Current revisions

- Repository: `osifeu-prog/slh-bot`
- Branch: `main`
- Latest Mini App authentication fix on `main`: `196e12a0c31a9bec43c6b92639806751638b921c` (`fix: authenticate Mini App tokenomics request`).
- Canonical production `web` is still running the previously verified successful deployment of the staking-hardening line (`c82a152...`) because the Mini App fix is currently **NEEDS_APPROVAL** in Railway.

## Runtime topology observed 2026-09-19

- `endearing-amazement/web`: latest deployment `NEEDS_APPROVAL`; persistent `/app/state` volume. The last verified successful production line remains active until the pending deployment is approved.
- `slh-cloud-bot/slh-cloud-bot`: API/control runtime; Telegram polling is disabled when `RUN_BOT != 1`.
- `slh-api/slh-api`: SUCCESS; separate API plane.
- `slh-api/Postgres`: SUCCESS.
- `slh-api/Redis`: SUCCESS.
- `slh-api/slh-air-bot`: SUCCESS.
- Legacy `TELEGRAM-BOT/Telegram_bot`: latest deployment FAILED; keep isolated until ownership/canonical-runtime decision is documented.

## Current integration boundary

The canonical web/Mini App and `slh-api` are both live, but they remain distinct runtime/data planes. The Mini App already reaches authenticated wallet/dashboard/exchange endpoints; the remaining integration work is to map identity, device registry ownership, and the AI intake/Bot Factory entry points before introducing or selecting another registry.

## Active integration rule

Do not create a new registry/store merely because a relationship is not yet visible. First locate the existing source of truth, document ownership, and only then change code.

## AI handoff contract

Every AI session should be able to answer:
1. What is canonical?
2. What changed?
3. What is verified?
4. What remains open?
5. What must not be mutated?
6. What is the next exact action?

No session should restart a completed investigation without reading this document and the relevant incident/work files.