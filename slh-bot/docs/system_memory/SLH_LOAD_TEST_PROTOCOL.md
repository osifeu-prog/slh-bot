# SLH Load Test Protocol v1.0

## Phase 0 – Health Check
- `/health`, `/testagents`
- Verify state volume is writable.

## Phase 1 – 10 Synthetic Users
- Create `test_user_001` … `test_user_010`.
- Validate count in `db.json`.

## Phase 2 – 50 Synthetic Users
- Create `test_user_011` … `test_user_060`.
- Monitor RAM and write latency.

## Phase 3 – 100 Synthetic Users
- Create `test_user_061` … `test_user_110`.
- Full system check: ASK, onboarding, agent messaging.

## Rollback
- Always keep a backup of `state/db.json` before each phase.
