# SLH Handler Manifest — 2026-09-22

## Purpose

Read-only inventory of the handler registration surface in `handlers/loader.py`. This is a consolidation aid, not a deletion authorization.

## Evidence levels

- **VERIFIED** — loader entry exists and the referenced module was fetched successfully from `main`.
- **LOADER-ONLY** — entry is present in the loader, but module existence/registration was not independently verified in this pass.
- **MISSING-PATH** — the expected path could not be fetched from `main` during this audit. This is a cleanup signal, not proof that the runtime cannot load it (the loader may reference an alternate module path).
- **SPECIAL** — registration is outside the normal `handlers.*` pattern or uses a special registration function.

## Canonical / Alpha-critical handlers verified

| Loader name | Module | Evidence | Role |
|---|---|---|---|
| onboarding | handlers.onboarding_v2 | VERIFIED | onboarding |
| join | handlers.join_handler | VERIFIED | /join |
| payment | handlers.payment_handler | VERIFIED | Stars/payment |
| stars_store | handlers.stars_store | VERIFIED | Stars store |
| academy | handlers.academy_handler | VERIFIED | Academy |
| staking | handlers.staking_handler | VERIFIED | staking |
| exec | handlers.exec_handler | VERIFIED | gated execution |
| admin | admin_handler | VERIFIED | control plane |
| stars_audit | handlers.stars_audit_handler | LOADER-ONLY | payment audit |
| agents | handlers.agents_handler | LOADER-ONLY | agents |
| wallet | handlers.wallet_handler | LOADER-ONLY | wallet |
| econ | econ_handler | LOADER-ONLY | economy |
| store | handlers.store_handler | LOADER-ONLY | store |
| webapp_data | handlers.webapp_data_handler | LOADER-ONLY | Mini-App |
| academy_menu | handlers.academy_menu_handler | LOADER-ONLY | Academy UI |
| learning_path | learning_path | LOADER-ONLY | learning path |
| lesson | handlers.lesson_handler | LOADER-ONLY | lessons |
| e | handlers.e_handler | LOADER-ONLY | control-plane gateway |
| exec_request | handlers.exec_request_handler | LOADER-ONLY | approval/request flow |
| gateway | handlers.gateway_handler | LOADER-ONLY | gateway |
| bot_identity | handlers.bot_identity_handler | LOADER-ONLY | bot identity |
| unified_system | handlers.unified_system_handler | LOADER-ONLY | system map |
| project | handlers.project_handler | LOADER-ONLY | project surface |
| me | handlers.me_handler | LOADER-ONLY | account read model |
| health_monitor | handlers.health_monitor_handler | LOADER-ONLY | health |
| progress | handlers.progress_handler | LOADER-ONLY | progress |
| staking_revenue | handlers.staking_revenue_handler | LOADER-ONLY | revenue/staking |

## High-priority cleanup observations

1. `admin_handler.py` is at the repository root, while the loader key is named `admin`. This is intentional in the current code and should not be "normalized" without testing.
2. The loader contains entries for `junk_handler`, `test_handler`, and `refresh_token_handler` under `handlers.*` paths that could not be fetched from `main` in this audit. These are **MISSING-PATH**, not approved deletions.
3. `brief_legacy` maps to `brief_handler`, so its loader name alone does not prove a separate legacy module exists.
4. `ton` maps to root-level `ton_handler`; `complete`, `diagnostic`, `guide`, `roadmap`, `sandbox`, etc. also map to root-level modules. These should be reviewed as a family before any move/removal.
5. The loader catches every module exception and continues. Therefore a skipped handler can be invisible at process level while the bot still reports "ALL HANDLERS READY". This is the strongest architectural cleanup/observability issue found in this pass.
6. The current loader has no machine-readable manifest, dependency graph, or explicit required/optional classification.

## Proposed disposition model

### KEEP
Required by the Golden Path, operational control plane, or active security/payment flows.

### REVIEW
Potentially active, but dependency/caller/runtime evidence is incomplete.

### ARCHIVE-CANDIDATE
Historical/support tooling with no demonstrated production dependency. Requires caller/runtime proof first.

### DELETE-CANDIDATE
Only after:
- no production caller;
- no registered route/callback;
- no test/CI dependency;
- no recovery/rollback role;
- no unique state/data dependency;
- replacement is verified on main.

## Immediate next engineering step

Build a machine-readable handler manifest from the loader and repository tree, then compare it with:
1. command/callback registrations;
2. imports/callers;
3. test/CI references;
4. Railway runtime logs;
5. Golden Path smoke tests.

Only after those five evidence sets agree should modules be archived or removed.

## Production safety

No production state, database, volume, Railway project, or main branch was changed by this manifest. The manifest belongs on the existing documentation branch until reviewed.
