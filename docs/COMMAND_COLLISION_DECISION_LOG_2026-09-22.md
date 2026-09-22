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
- `handlers/help_handler.py` currently documents `/complete` as task completion, while the Academy implementation also owns that same command.

## Decision

### /complete — HOLD / DO NOT DELETE

There are two incompatible contracts:
1. Academy compatibility: `/complete <stage>` or `/complete <course_id> <stage>`.
2. Task completion: `/complete <task_id>`.

The canonical Academy path already has an explicit `/finish <course_id> <stage>` command. Therefore the likely cleanup direction is to retire the Academy compatibility command and preserve a single task-oriented `/complete` — **but this is a proposed direction, not an executed change**.

Before changing anything:
- inspect task handler/tests/docs for `/complete <task_id>`;
- inspect Academy tests/docs/inline keyboards for the compatibility form;
- verify no external automation invokes the Academy form;
- run the Alpha Academy E2E path using `/finish`;
- only then remove the obsolete registration.

### /brief — HOLD / DO NOT DELETE

The loader registers both `brief` and `brief_legacy`, and both resolve to the same root module `brief_handler.py`. This is a concrete duplicate registration.

Before removing `brief_legacy`:
- verify the loader key is not referenced by code or deployment tooling;
- confirm `/brief` still registers once after removing the duplicate;
- verify `/valuation` and `/onchain` remain registered from `handlers.brief_handler`;
- perform a production-safe smoke test.

### /self_test — ARCHIVE-CANDIDATE, NOT DELETE

The Telegram command is legacy-looking and separate from the canonical pytest/CI path, but it remains explicitly loaded. Retirement requires caller and rollback evidence.

## Loader readiness — HIGH PRIORITY

The loader catches all module exceptions and still emits `ALL HANDLERS READY`. This should be corrected before broad cleanup because otherwise a cleanup can accidentally hide a broken required handler.

Target behavior:
- REQUIRED handler failure => readiness failure / startup failure.
- OPTIONAL handler failure => structured warning.
- Report: loaded / skipped / failed / required_failed.
- No unconditional `ALL HANDLERS READY`.

No production or main-branch change was made by this document.