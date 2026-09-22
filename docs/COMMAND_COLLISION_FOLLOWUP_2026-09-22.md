# Command Collision Follow-up — 2026-09-22

## /complete — HIGH PRIORITY

Two independently registered handlers exist in the current source:

1. `handlers/academy_handler.py`
   - Registers `/complete`.
   - Semantics: complete an Academy lesson.
   - Accepted forms: `/complete <stage>` using active course, or `/complete <course_id> <stage>`.
   - Delegates to `core.lesson_engine.complete_lesson`.
   - This is compatible with the canonical `/lesson → /finish` Academy flow, but duplicates completion semantics.

2. `complete_handler.py`
   - Registers `/complete`.
   - Semantics: complete an internal task.
   - Accepted form: `/complete <task_id>`.
   - Delegates to `internal_agent.complete_task`.

### Important consequence

The two handlers cannot safely share one public command contract. A one-argument invocation such as `/complete 1` is syntactically valid for both handlers but means different things.

The current public `/help` text also describes `/complete` as task completion, while the Academy source uses it for lesson completion.

### Recommended migration direction

Do not delete either implementation yet.

First establish the intended public API:

- Canonical Academy completion: already has explicit `/finish <course_id> <stage>` and inline callback `slh_finish_<course>_<stage>`.
- Task completion: `/complete <task_id>` is the legacy task contract shown in help.

If tests/callers confirm task completion is still needed, a clean migration is to reserve `/complete` for tasks and retire the Academy compatibility alias, while keeping `/finish` as the sole Academy command. This is a migration proposal, not a production change.

## /brief — HIGH CONFIDENCE DUPLICATE

`handlers/brief_handler.py` and root `brief_handler.py` both register `/brief`.

The implementations are materially different:

- `handlers/brief_handler.py`: uses `core.morning_brief.get_morning_brief(uid)`; same module also owns `/valuation` and `/onchain`.
- root `brief_handler.py`: directly reads `journal.json`, `ROADMAP.md`, and `state_manager`.

The loader audit already confirms both loader entries exist. Therefore this is not merely duplicate source naming.

The canonicalization decision should be based on which data contract is currently used by the active UI/operations. Do not remove the legacy loader entry until that dependency check is complete.

## Search limitation

GitHub connector code-search returned zero results for several exact `/complete` and callback queries. This is weak negative evidence because connector search did not expose matching code; it is not proof that callers do not exist.

The stronger evidence above comes from direct source fetches of the actual handler modules and the loader audit.

## Immediate non-destructive actions

1. Search tests/docs/inline keyboards for task completion callers using broader local/repository inspection.
2. Verify whether `/finish` fully covers all Academy completion use cases.
3. Identify the intended `/brief` output contract.
4. Only after evidence is complete, propose one small migration PR.
5. No production or main-branch change is authorized by this audit.
