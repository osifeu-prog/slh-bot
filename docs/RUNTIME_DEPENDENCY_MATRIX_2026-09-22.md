# SLH Runtime Dependency Matrix — 2026-09-22

## Scope
Read-only consolidation audit of the canonical `main` tree. This document records evidence and disposition candidates; it does not authorize deletion or production changes.

## Runtime spine
`start_railway.sh` → `bot_gateway.py` → `handlers.loader.load_handlers()`.
`bot_gateway.py` also boots the agent runtime and mounts the web application/control-plane routes.

## Critical loader observation
The loader iterates a large module list and catches every import/registration exception, prints `<name> skipped`, and continues to `ALL HANDLERS READY`. Therefore process health alone cannot prove that every registered route is active.

## Candidate classification

| Path | Loader/runtime evidence | Direct role observed | Disposition |
|---|---|---|---|
| `handlers/loader.py` | Directly imported by gateway | Registers production handlers | KEEP / critical |
| `start_railway.sh` | Railway entrypoint | Starts canonical gateway | KEEP / critical |
| `bot_gateway.py` | Canonical process | API + Telegram polling + handler loading | KEEP / critical |
| `refresh_token_handler.py` | Explicit loader entry `refresh` | Admin-only token-control metadata/rotation instructions | KEEP / security/control |
| `slh_autopilot.py` | Not part of loader | Legacy standalone health/fix script; `--fix` can start bot, edit files, commit/push | ARCHIVE-CANDIDATE; do not execute |
| `slh_consolidate.py` | Not part of loader | Standalone state/agents mirror writer with backup | REVIEW; state mutation |
| `slh_sync_fix.py` | Not part of loader | Standalone agents mirror normalizer/writer with backup | REVIEW; state mutation |
| `slh_clean_inventory.py` | Not part of loader | Inventory/reporting utility | ARCHIVE-CANDIDATE pending caller check |
| `junk_handler.py` | Explicit loader entry `junk` | Admin scan/backup/delete commands; also sandbox file scan | REVIEW / high-risk legacy |
| `test_handler.py` | Explicit loader entry `test` | Registers `/self_test` via `self_test.test_all` | REVIEW; preserve until replacement/equivalent verified |
| `sandbox_handler.py` | Explicit loader entry `sandbox` | Executes allowlisted commands through proot | REVIEW / security-sensitive |
| `complete_handler.py` | Explicit loader entry `complete` | Completes tasks through `internal_agent` | REVIEW; unknown dependency |
| `diagnostic_handler.py` | Explicit loader entry `diagnostic` | Calls external `~/slh_clean/diag_scan.sh` | ARCHIVE-CANDIDATE if no deployed filesystem dependency |
| `guide_handler.py` | Explicit loader entry `guide` | Static help menu + callbacks | REVIEW; likely supersedable by canonical help/UI |
| `roadmap_handler.py` | Explicit loader entry `roadmap` | Reads root `ROADMAP.md` | REVIEW; documentation surface |
| `devsetup_handler.py` | Explicit loader entry `devsetup` | Sends developer setup instructions + `SESSION_STATUS.md` | REVIEW; operator tooling |
| `ton_handler.py` | Explicit loader entry `ton` | Root-level TON handler | REVIEW; loader mapping is intentionally nonstandard |
| `brief_handler.py` | Loaded twice: `brief` + `brief_legacy` | Same module registered under two loader keys | REVIEW for duplicate registration |

## Important findings
1. The presence of a loader entry is evidence of intended runtime registration, not proof that the handler successfully loaded in production.
2. Search for candidate names/imports returned no repository search hits beyond the files themselves. This search result is weak evidence and is not sufficient for deletion.
3. `slh_autopilot.py` is especially unsuitable for casual execution: its fix path can launch `bot_stable.py`, modify files, commit, and push.
4. `junk_handler.py` and `sandbox_handler.py` expose filesystem/process capabilities and should be treated as security-sensitive until replaced or explicitly retained.
5. `refresh_token_handler.py` is not obsolete merely because its filename says refresh; its current implementation is a centralized, non-secret token-control surface and is part of the loader.
6. `brief` and `brief_legacy` point to the same module and require duplicate-registration verification before consolidation.

## Next audit
Before any deletion/archive:
- compare loader registrations with actual command/callback decorators;
- inspect imports/callers and CI/workflow references;
- identify filesystem/runtime dependencies outside the repository;
- verify Golden Path routes: `/start`, `/join`, agent creation, Academy, Stars payment, `/stake`, `/unstake`;
- classify each candidate as KEEP / REVIEW / ARCHIVE-CANDIDATE only after evidence;
- only then prepare a separate cleanup PR/branch.

## Safety boundary
No production DB, Railway service, volume, main branch, or user state was changed by this audit.
