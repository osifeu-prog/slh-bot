# Alpha Control Plane

`core/alpha_control_plane.py` is the deterministic source of truth for Alpha readiness.

## Commands

- `/alpha_status` — owner-only, read-only readiness report.
- `/alpha_open` — owner-only state transition; succeeds only when the evaluator returns `READY`.
- `/alpha_state` — owner-only view of the persisted Alpha state.
- `/exec alpha_status` and `/exec alpha_open` are supported aliases through the gated executor.

## Rule

A feature is an Alpha blocker only when it affects runtime safety, canonical state/economy integrity, payments, SLH integrity/transfers, exchange settlement, staking availability, or basic onboarding. Nice-to-have improvements remain post-Alpha work.
