# SLH Control Plane

Canonical coordination layer for SLH OS development, runtime, and release work.

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
