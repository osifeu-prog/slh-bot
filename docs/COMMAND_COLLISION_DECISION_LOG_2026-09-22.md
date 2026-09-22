# Command Collision Decision Log — 2026-09-22

## Evidence reviewed

Current loader (`handlers/loader.py`) registers:
- `academy → handlers.academy_handler`
- `lesson → handlers.lesson_handler`
- `brief → handlers.brief_handler`
- `brief_legacy → brief_handler`
- `complete → complete_handler`

Source inspection confirms:
- `handlers.academy_handler` registers `/complete` and delegates to `core.lesson_engine.complete_lesson`.
- `handlers.lesson_handler` registers `/finish` and delegates to the same `core.lesson_engine.complete_lesson`.
- `complete_handler` registers `/complete` and delegates to `internal_agent.complete_task`.
- `handlers/task_handler.py` has a separate task-completion surface: `/task_done <task_id>`, backed by `core.task_completion_service.complete_task`.
- `tests/test_academy_progression.py` verifies Academy progression and `lesson_engine` sequencing, but does not exercise the `/complete` command compatibility surface.
- `tests/test_join_onboarding.py` verifies the new-user onboarding path through profile, agent creation, rewards, and Academy start; it does not exercise `/complete`.
- `handlers/help_handler.py` currently documents `/complete` as task completion, while the Academy implementation also owns that same command.
- No dedicated `test_task_completion*.py` file was found at the expected paths during this targeted audit. This is not exhaustive proof that no other test covers it.

For `/brief`:
- `handlers.brief_handler` is one implementation. It registers `/brief`, `/valuation`, and `/onchain`, using the newer `core.morning_brief`, `core.ton_lab`, and `core.deposit_monitor` surfaces.
- Root `brief_handler.py` is a different implementation. It also registers `/brief`, but reads `journal.json`, `ROADMAP.md`, and state-manager data and emits a legacy-style status report.
- Therefore `/brief` is not merely two registrations of the same implementation: it is a real route collision between two different implementations.

## Decision

### /complete — HOLD / DO NOT DELETE

There are two incompatible contracts:
1. Academy compatibility: `/complete <stage>` or `/complete <course_id> <stage>`.
2. Task-oriented completion: `/complete <task_id>`.

The canonical Academy path already has an explicit `/finish <course_id> <stage>` command, while the help surface describes `/complete` as task completion. The separate canonical task handler currently uses `/task_done <task_id>`, so the task-command contract is itself not fully consolidated.

The likely cleanup direction remains to make Academy completion exclusively `/finish` and then choose one task-completion command contract — but this is a proposed direction, not an executed change.

Before changing anything:
- inspect all task-related tests and callers for `complete_handler`, `internal_agent.complete_task`, and `task_completion_service.complete_task`;
- inspect Academy tests/docs/inline keyboards for the compatibility form;
- verify no external automation invokes the Academy `/complete` form;
- run the Alpha Academy E2E path using `/finish`;
- decide explicitly whether `/complete` or `/task_done` is the canonical task command;
- only then remove the obsolete registration.

### /brief — HOLD / DO NOT DELETE

The loader registers `brief` and `brief_legacy`, which resolve to two different implementations that both register `/brief`.

Before removing or renaming either registration:
- identify all callers/docs/tooling that expect the legacy status-style `/brief`;
- confirm the newer `handlers.brief_handler` behavior is the intended canonical surface;
- confirm `/valuation` and `/onchain` remain registered from `handlers.brief_handler`;
- perform a production-safe smoke test that confirms `/brief` registers exactly once and returns the intended report;
- only then retire the duplicate route.

### /self_test — ARCHIVE-CANDIDATE, NOT DELETE

The Telegram command is legacy-looking and separate from the canonical pytest/CI path, but it remains explicitly loaded. Retirement requires caller and rollback evidence.

## Loader readiness — HIGH PRIORITY

The loader catches all module exceptions and still emits `ALL HANDLERS READY`. This should be corrected before broad cleanup because otherwise a cleanup can accidentally hide a broken required handler.

Target behavior:
- REQUIRED handler failure => readiness failure / startup failure.
- OPTIONAL handler failure => structured warning.
- Report: loaded / skipped / failed / required_failed.
- No unconditional `ALL HANDLERS READY`.

## Current status

No production or main-branch change was made by this document. This evidence update is limited to the existing `docs/system-census-20260922` audit branch.
