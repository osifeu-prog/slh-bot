# SLH Launch Documentation Index

## Canonical source of truth

The active launch plan is:

`LAUNCH_PLAN.json`

The progress/ETA engine is:

`tools/slh_launch_control.py`

These two files define the current launch state.

## Historical / supporting documents

The following documents are retained as historical evidence and are
NOT independent launch plans:

- `ROADMAP.md` — historical/supporting record
- `SLH_V1.2_ROADMAP.md` — historical/supporting record
- `NEXT_STEPS.md` — historical/supporting record
- `STATUS.md` — historical/supporting record
- `SESSION_STATUS.md` — historical/supporting record
- `RELEASE_STATUS.md` — not present in current checkout
- `RELEASE_STATUS_2026_07_21.md` — historical/supporting record
- `STABLE_STATUS_20260713.txt` — historical/supporting record
- `docs/system_memory/SLH_STABLE_GATEWAY_MILESTONE_20260713.md` — historical/supporting record

## Control-plane evidence

- `_slh_map/control/LAUNCH.json`
- `_slh_map/control/LAUNCH_EVIDENCE.json`
- `_slh_map/control/CONTROL_STATE.json`
- `_slh_map/control/JOURNAL.jsonl`

These are evidence/state artifacts. They do not override `LAUNCH_PLAN.json`.

## Rule

Do not create another independent roadmap.

If a historical document contains an old TODO or estimate, it remains
historical unless explicitly migrated into `LAUNCH_PLAN.json`.
