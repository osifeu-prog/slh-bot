# SLH Active Work

Updated: 2026-09-19

## Track A — Control Plane / AI synchronization

- [x] Define canonical source-of-truth boundaries.
- [x] Define AI handoff contract.
- [ ] Add automated status snapshot generation.
- [ ] Add unified service/deployment inventory.
- [ ] Add release readiness report.

## Track B — Data integrity

- [x] Atomic DB save + anti-wipe guard committed.
- [x] Reconciler migrated to `state_manager.atomic_update()` (PR #84 merged).
- [x] Verify DB survival after deploy.
- [x] Reconcile proven 240 SLH staking-counter gap.
- [x] Document and correct the 44M SLH token-balance provenance incident.
- [ ] Define one canonical economy ledger/data plane.

## Track C — Identity / Agents / Devices

- [x] User identity exists.
- [x] Agent registry and ownership exist.
- [x] Device ownership exists.
- [ ] Map existing API/Postgres Device Registry.
- [ ] Prove or implement canonical Agent↔Device binding.

## Track D — Product release / integration

- [ ] Promote the Mini App tokenomics authentication fix from `main` to production (Railway deployment currently `NEEDS_APPROVAL`).
- [ ] Consolidate Website + Mini App + intake AI + Bot Factory entry points.
- [ ] Verify public domains and production routing.
- [ ] Build release checklist from the same canonical state.
- [ ] Publish only features whose runtime, data path, and rollback are verified.

## Current deployment state

The old `slh-cloud-bot` watcher blocker was corrected; its watch patterns are no longer `__NEVER_BUILD__/**`. Do not create a duplicate service or rotate production secrets merely to bypass a deployment state.

The canonical `web` service currently has a pending Railway deployment for the Mini App auth fix. It has no snapshot yet and cannot be redeployed through the snapshot-based redeploy path while it remains `NEEDS_APPROVAL`.

## Next exact actions

1. Resolve the explicit Railway approval for the Mini App auth fix.
2. Verify the resulting production deployment and Mini App `/api/v1/tokenomics` path.
3. Map `slh-api` identity/device ownership against the canonical bot state.
4. Identify the actual Website → AI intake → Bot Factory routing and ownership.
5. Record the unified map and release readiness state in Control Plane docs.

## Rule

Do not create duplicate infrastructure while an existing service may already be authoritative. Prefer integration, migration, or explicit deprecation over another parallel implementation.
