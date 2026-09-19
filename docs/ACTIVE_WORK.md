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

## Track D — Product release

- [ ] Consolidate Website + Mini App + intake AI + Bot Factory entry points.
- [ ] Verify public domains and production routing.
- [ ] Build release checklist from the same canonical state.
- [ ] Publish only features whose runtime, data path, and rollback are verified.

## Current deployment blocker

The canonical `slh-cloud-bot` Railway service is connected to `osifeu-prog/slh-bot` / `main`, but its previous build watcher was `__NEVER_BUILD__/**`, which prevented Git-triggered builds. The watcher has been corrected to `**`.

The service's latest historical deployment was `SKIPPED` without a build snapshot, so Railway's redeploy operation cannot copy it. A fresh Git-source deployment is still required to prove that the merged `main` commit is running in the existing service. Do not create a duplicate service or change production secrets merely to bypass this.

## Rule

Do not create duplicate infrastructure while an existing service may already be authoritative. Prefer integration, migration, or explicit deprecation over another parallel implementation.
