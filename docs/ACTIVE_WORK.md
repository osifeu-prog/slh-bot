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
- [x] Verify DB survival after deploy.
- [x] Reconcile proven 240 SLH staking-counter gap.
- [ ] Complete token-balance provenance audit.
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

## Rule

Do not create duplicate infrastructure while an existing service may already be authoritative. Prefer integration, migration, or explicit deprecation over another parallel implementation.
