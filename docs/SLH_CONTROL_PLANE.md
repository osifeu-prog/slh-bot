# SLH Control Plane

Canonical coordination layer for SLH OS development, runtime, and release work.

## Source-of-truth boundaries

- **GitHub**: versioned code, configuration, documentation, review and release history.
- **Railway**: runtime/deployment state and infrastructure topology.
- **SLH Bot state**: `state/db.json` is the current bot data plane; writes must go through the canonical state manager.
- **SLH API/Postgres**: separate API/data plane; must be mapped before declaring it authoritative for any entity.
- **AI sessions**: workers/clients of the Control Plane. They do not create competing canonical state.

## Current canonical bot revision

- Repository: `osifeu-prog/slh-bot`
- Branch: `main`
- Latest verified commit: `592f1a54e0ca4f10d7edb6047547ac0c543c269f`
- Change: atomic `save_db` with anti-wipe guard.

## Runtime topology observed 2026-09-19

- `endearing-amazement/web`: SUCCESS; persistent `/app/state` volume.
- `slh-cloud-bot/slh-cloud-bot`: SUCCESS; API gateway/runtime present, Telegram bot disabled when `RUN_BOT != 1`.
- `slh-api/slh-api`: SUCCESS; separate API plane.
- `slh-api/Postgres`: SUCCESS.
- `slh-api/Redis`: SUCCESS.
- `slh-api/slh-air-bot`: SUCCESS.
- Legacy `TELEGRAM-BOT/Telegram_bot`: latest deployment FAILED; keep isolated until ownership/canonical-runtime decision is documented.

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
