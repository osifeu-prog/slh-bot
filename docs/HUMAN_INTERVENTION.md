# Human intervention controls (scoped rollout)

## Scope

This change applies approval gates at the supported mission/task authorities:
- `mission_execute` before invoking a runtime agent for an assigned mission.
- `mission_complete` before changing a verified executed mission to completed and issuing the completion reward.
- `task_complete` before completion state/reward writes.

It is **not** a universal intercept for every mutating command, all `/e` shell commands, deployments, settlement, or arbitrary system actions. Unknown action IDs are refused by the approval authority, but actions not yet wired to that authority are not covered by this scoped rollout. Each additional side-effect path must be integrated and tested before claiming global coverage.

## Default policy

The effective default is approval required for both `action_execution` and `action_completion`. Missing/corrupt DB policy or a failed state read cannot enable bypass. Defaults are read-only; they are not written until the owner saves a setting.

## Owner commands (private chat only)

- `/config status` — inspect the effective policy.
- `/config add action_execution` — persist approval required before mission execution.
- `/config add action_completion` — persist approval required before mission/task completion.
- `/config set action_execution on` or `/config set action_completion on` — turn a gate on.
- `/config set <setting> off` — create a short-lived disable-confirmation request.
- `/config confirm <confirmation_id>` — second explicit owner confirmation to disable a gate.
- `/approve_action <request_id>` / `/reject_action <request_id>` — decide a pending action.

Pending approvals expire after 30 minutes and bind the exact action, resource and requester. A request may be consumed once only. Disabling a gate requires a second explicit confirmation within five minutes. Every setting change and approval transition is written to the canonical DB audit list.

## Release requirements

Run the new unit tests and the repository regression/CI suite. Independently review every execution/completion path and approval-state transition. Do not merge/deploy this PR without approval. This code change does not modify Production state, wallet balances, Exchange, BNB or TON settlement flags.
