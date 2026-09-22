# SLH Runtime Dependency Matrix — 2026-09-22

## Scope
Read-only consolidation audit of the canonical `main` tree. This document records evidence and disposition candidates; it does not authorize deletion or production changes.

## Runtime spine
`start_railway.sh` → `bot_gateway.py` → `handlers.loader.load_handlers()`.
`bot_gateway.py` also boots the agent runtime and mounts the web application/control-plane routes.

## CI / deployment evidence
- `.github/workflows/ci.yml` compiles essentially every Python file outside `_slh_audit`, `_archive`, and state, then verifies current Stars, Academy, economy, Control Plane, token-control, MCP and MQTT contracts.
- `.github/workflows/deploy.yml` performs another repository-wide Python compile and validates the current integration contracts before handing off to Railway.
- `.github/workflows/full-regression.yml` runs the `tests/` suite on main pushes and pull requests.
- None of the reviewed workflows invokes `slh_autopilot.py`, `slh_consolidate.py`, `slh_sync_fix.py`, `slh_clean_inventory.py`, `self_test.py`, or the reviewed legacy handlers directly.
- GitHub code search returned no caller/import matches for the reviewed candidate filenames. Because connector code search produced empty results, this is **weak negative evidence**, not proof of zero callers.

## Critical loader observation
The loader iterates a large module list and catches every import/registration exception, prints `<name> skipped`, and continues to `ALL HANDLERS READY`. Therefore process health alone cannot prove that every registered route is active.

## Candidate classification

| Path | Loader/runtime evidence | Direct role observed | Disposition |
|---|---|---|---|
| `handlers/loader.py` | Directly imported by gateway | Registers production handlers | KEEP / critical |
| `start_railway.sh` | Railway entrypoint | Starts canonical gateway | KEEP / critical |
| `bot_gateway.py` | Canonical process | API + Telegram polling + handler loading | KEEP / critical |
| `refresh_token_handler.py` | Explicit loader entry `refresh` | Admin-only token-control metadata/rotation instructions | KEEP / security/control |
| `slh_autopilot.py` | Not part of loader; not referenced by reviewed CI | Legacy health/fix script; `--fix` can start bot, edit files, commit/push | ARCHIVE-CANDIDATE; do not execute |
| `slh_consolidate.py` | Not part of loader; not referenced by reviewed CI | Standalone state/agents mirror writer with backup | REVIEW; state mutation |
| `slh_sync_fix.py` | Not part of loader; not referenced by reviewed CI | Standalone agents mirror normalizer/writer with backup | REVIEW; state mutation |
| `slh_clean_inventory.py` | Not part of loader; not referenced by reviewed CI | Inventory/reporting utility | ARCHIVE-CANDIDATE pending filesystem/caller check |
| `junk_handler.py` | Explicit loader entry `junk` | Admin scan/backup/delete commands; sandbox file scan | REVIEW / high-risk legacy |
| `test_handler.py` | Explicit loader entry `test` | Registers `/self_test` via `self_test.test_all` | REVIEW / stale-test risk |
| `sandbox_handler.py` | Explicit loader entry `sandbox` | Executes allowlisted commands through proot | REVIEW / security-sensitive |
| `complete_handler.py` | Explicit loader entry `complete` | Completes tasks through `internal_agent` | REVIEW; unknown dependency |
| `diagnostic_handler.py` | Explicit loader entry `diagnostic` | Calls external `~/slh_clean/diag_scan.sh` | ARCHIVE-CANDIDATE if no deployed filesystem dependency |
| `guide_handler.py` | Explicit loader entry `guide` | Static help menu + callbacks | REVIEW; likely supersedable by canonical help/UI |
| `roadmap_handler.py` | Explicit loader entry `roadmap` | Reads root `ROADMAP.md` | REVIEW; documentation surface |
| `devsetup_handler.py` | Explicit loader entry `devsetup` | Sends developer setup instructions + `SESSION_STATUS.md` | REVIEW; operator tooling |
| `ton_handler.py` | Explicit loader entry `ton` | Root-level TON handler | REVIEW; loader mapping is intentionally nonstandard |
| `brief_handler.py` | Loaded twice: `brief` + `brief_legacy` | Same module registered under two loader keys | REVIEW for duplicate registration |

## New evidence: stale legacy test surface
`test_handler.py` calls `self_test.test_all()`. That test checks for `bot_stable.py`, root-level `db.json`, Ollama, and a `mytermux` agent path. The canonical production process is now `bot_gateway.py`, while the repository CI/full regression uses the `tests/` suite. This makes `/self_test` a strong candidate for replacement or removal, but **not yet deletion**, because the command is still explicitly registered by the loader.

## Important findings
1. A loader entry is evidence of intended runtime registration, not proof that the handler successfully loaded in production.
2. CI is protecting the current architecture through repository-wide compilation and targeted contract tests; deleting arbitrary Python files can therefore fail CI even when the file is not a runtime dependency.
3. `slh_autopilot.py` is especially unsuitable for casual execution: its fix path can launch `bot_stable.py`, modify files, commit, and push.
4. `slh_consolidate.py` and `slh_sync_fix.py` directly write state mirrors. They must not be run as cleanup utilities against production without a separate state-authority decision.
5. `junk_handler.py` and `sandbox_handler.py` expose filesystem/process capabilities and should be treated as security-sensitive until replaced or explicitly retained.
6. `refresh_token_handler.py` is not obsolete merely because its filename says refresh; its current implementation is a centralized, non-secret token-control surface and is part of the loader.
7. `brief` and `brief_legacy` point to the same module and require duplicate-registration verification before consolidation.
8. `SESSION_STATUS.md` and `ROADMAP.md` contain substantial historical claims from July/August and should not be treated as authoritative current-state documentation without reconciliation against the 2026-09-22 census.

## Next audit
Before any deletion/archive:
- compare loader registrations with actual command/callback decorators;
- inspect imports/callers and CI/workflow references;
- identify filesystem/runtime dependencies outside the repository;
- inspect duplicate registration risk for `brief` and other aliases;
- verify Golden Path routes: `/start`, `/join`, agent creation, Academy, Stars payment, `/stake`, `/unstake`;
- classify each candidate as KEEP / REVIEW / ARCHIVE-CANDIDATE only after evidence;
- only then prepare a separate cleanup PR/branch.

## Safety boundary
No production DB, Railway service, volume, main branch, or user state was changed by this audit.
