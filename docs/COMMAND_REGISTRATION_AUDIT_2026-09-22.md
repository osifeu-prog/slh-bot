# Command Registration Audit — 2026-09-22

## Scope
Read-only audit of the canonical `osifeu-prog/slh-bot` `main` branch, focused on loader registration, Alpha Golden Path commands, and obvious duplicate registrations.

## Evidence

| Surface | Evidence | Finding |
|---|---|---|
| Loader | `handlers/loader.py` | The loader registers 100+ modules and accepts several registration conventions. Every import/registration exception is caught and only logged as "skipped"; startup then prints "ALL HANDLERS READY". |
| /start | `handlers/onboarding_v2.py:116` | Canonical /start registration is in onboarding_v2, which is loaded by the loader under `onboarding`. |
| /join | `handlers/join_handler.py` | Canonical /join registration is in join_handler, loaded once under `join`. |
| /pay | `handlers/payment_handler.py:72` | Canonical /pay registration is in payment_handler; loader loads payment once. payment_handler exposes `register_payment_handlers()` and a `register()` wrapper. |
| /stake | `handlers/staking_handler.py:13` | Canonical /stake registration is in staking_handler, loaded once under `staking`. |
| /admin | `admin_handler.py` | Canonical /admin registration is in root-level admin_handler, loaded once under `admin`. |
| /help | `handlers/help_handler.py` | Canonical /help registration is in help_handler, loaded once under `help`. |
| /guide | `guide_handler.py` | Canonical /guide registration is root-level and loaded once under `guide`. |
| /brief | `handlers/loader.py` | **Confirmed duplicate loader registration:** both `("brief", "handlers.brief_handler")` and `("brief_legacy", "brief_handler")` are present. Both resolve to the same `brief_handler.py` module and expose `init(bot)`, so the same /brief handler is registered twice. |
| /self_test | `test_handler.py` | `/self_test` calls legacy `self_test.test_all()`. The file is explicitly loaded as `test`. This remains a cleanup candidate, not an authorized deletion. |
| /exec | `handlers/exec_handler.py` | Canonical /exec is gated through `core.exec_policy`; no duplicate was established in this audit. |

## Important architecture finding

The loader is currently an observability weak point. A module can fail import/registration, be reported as "skipped", and the process continues to the unconditional `ALL HANDLERS READY` message. Therefore process health must not be treated as proof that every registered command exists.

## Duplicate / legacy findings

### Confirmed duplicate
- `brief` and `brief_legacy` both load the same root `brief_handler.py`.
- This is a registration duplicate, not merely two files with similar names.
- Safe next step: remove the duplicate loader entry only after a read-only runtime/CI check confirms no code depends on the loader key name `brief_legacy`. No production change was made by this audit.

### Legacy candidate
- `test_handler.py` exposes `/self_test` and imports `self_test.test_all`.
- Existing regression CI uses the repository test suite rather than this Telegram command.
- Earlier dependency review found the self-test checks old assumptions such as `bot_stable.py`; therefore it is a strong archive/replacement candidate, but deletion still requires caller/route/rollback evidence.

## Golden Path status from source audit

The canonical source path is coherent at the registration level:

`/start → /join → personal agent/profile → Academy → /pay → Credits → /stake`

- /start is owned by onboarding_v2.
- /join is owned by join_handler.
- /pay is owned by payment_handler and uses the canonical Stars price authority.
- /stake is owned by staking_handler.

This audit verifies source registration, not live Telegram E2E behavior. A live Alpha gate still needs to verify the actual bot instance, real user flow, Telegram Stars pre-checkout/successful-payment callbacks, credit fulfillment, and stake/unstake behavior.

## Next cleanup order

1. Add machine-readable loader manifest with required/optional classification.
2. Change loader reporting so skipped required handlers fail startup/readiness rather than being hidden by "ALL HANDLERS READY".
3. Remove/retire the duplicate `brief_legacy` registration after dependency confirmation.
4. Retire `/self_test` only after the canonical CI/doctor path is confirmed as its replacement.
5. Continue command/callback collision audit for callback prefixes and non-loader registrations.
6. Only then begin archive/delete candidates. No live DB, Railway service, main branch, or production state was changed in this audit.


## Follow-up collision finding — /complete

A deeper inspection confirmed a second command collision that should be treated as HIGH PRIORITY REVIEW:

- `handlers.academy_handler.register` registers `/complete` for Academy lesson completion and routes to `core.lesson_engine.complete_lesson`.
- `complete_handler.init` also registers `/complete`, but interprets the argument as a task ID and calls `internal_agent.complete_task`.
- The loader registers both modules: `academy` and `complete`.

These are two different semantic contracts under the same Telegram command. This is more serious than the `/brief` duplicate because the implementations can produce different outcomes for the same input.

**Do not delete either implementation yet.** First map:
1. callers/tests using `/complete <task_id>`;
2. Academy compatibility usage of `/complete <stage>` and `/complete <course_id> <stage>`;
3. any inline keyboards or documentation that emit the command;
4. whether a command split or explicit dispatcher is the safer migration.

Recommended eventual shape: one canonical command owner, with distinct explicit commands for task completion and lesson completion if both capabilities are still required.

## Follow-up runtime-authority finding

`bot_gateway.py` is the current canonical startup path: it imports `handlers.loader.load_handlers` and starts the primary bot. `bot_stable.py` contains additional legacy command registrations, including `/test`, but is not the startup path used by the canonical Railway service.

Therefore source-code presence in `bot_stable.py` must not be treated as proof that those commands are active in production.
