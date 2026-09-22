# Machine-Readable Command/Callback Manifest — 2026-09-22

This manifest is intentionally evidence-conservative. It records only command/callback surfaces verified from the current loader and targeted source inspection. It is **not** an exhaustive proof that no other registrations exist.

Canonical runtime: `bot_gateway.py → handlers.loader.load_handlers`  
Audited source: `main@96990e1aae5d52da4d01221868514eaa2c464ce1`

## High-confidence command ownership

| Command | Owner | Status |
|---|---|---|
| /start | handlers.onboarding_v2 | KEEP |
| /join | handlers.join_handler | KEEP |
| /pay | handlers.payment_handler | KEEP |
| /stake, /unstake | handlers.staking_handler | KEEP |
| /academy | handlers.academy_menu_handler | KEEP |
| /lesson, /finish | handlers.lesson_handler | KEEP |
| /help | handlers.help_handler | KEEP |
| /admin | admin_handler | KEEP |
| /exec | handlers.exec_handler | KEEP |
| /brief | handlers.brief_handler + brief_handler | REVIEW — duplicate registration surface |
| /complete | handlers.academy_handler + complete_handler | REVIEW — semantic collision |
| /self_test | test_handler | ARCHIVE-CANDIDATE |

## Callback surface verified

- onboarding: `start_join`, `show_help`, `continue_course`, `menu_wallet`, `menu_agents`, `menu_ai`, `menu_missions`, `menu_share`, `system_status`, `goto_dashboard`, `create_agent`
- Academy: `slh_academy`, `academy_<course>`, `slh_lesson_<course>_<stage>`, `slh_finish_<course>_<stage>`
- legacy onboarding callback: `onboard_start`

No callback collision is declared yet from this targeted set. A complete scan of all loaded handler sources remains required.

## Critical next actions

1. Resolve /brief duplicate ownership.
2. Map /complete callers, inline keyboards, tests and documentation before deciding whether to split the command.
3. Replace loader's unconditional readiness claim with required/optional readiness reporting.
4. Complete callback-prefix scan across every loaded handler.
5. Only after those checks, classify files for archive/delete.

No production state, Railway service, database, or main branch was changed by this audit.
