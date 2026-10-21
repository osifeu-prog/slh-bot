# Community Alpha: verified free access, Academy sync, feedback and developer audits

Status: planning document only. This file does not change runtime behavior, course prices, user roles, production state, or public announcements.

## 1. Public claims that are currently safe

Based on `courses.json` on `main`:

| Course ID | Display title | Access in catalog | Lessons |
|---|---|---:|---:|
| `bitcoin_mastery` | ביטקוין מאסטרי | free | 12 |
| `ai_tokens` | טוקנים ב-AI — שיטת עבודה בהשראת בלוקצ׳יין | free | 12 |
| `governance_game_theory` | ממשל, תורת המשחקים וכלכלה מבוזרת | free | 8 |
| `ethereum` | אתריום מאסטרי | paid | 5 |
| `slh_vs_eth_sol` | SLH vs Ethereum vs Solana | paid | 5 |
| `algo_trading_999` | מסחר אלגוריתמי, כוחות השוק ופסיכולוגיה | paid | 7 |

The Telegram snapshot supplied by the owner shows 39 users, 17 registered users, 16 new visits in 30 days, 10 revenue events totaling 1,522 XTR, and 5 fulfilled Stars orders. These are snapshot figures, not guaranteed current figures; XTR is Telegram Stars, not fiat currency or net bank proceeds.

Do **not** say every product or every service is free. The catalog explicitly marks three courses as paid, and the commerce report lists paid Stars products. A safe public message may say that SLH Spark is inviting users to try its free learning content and available bot features, while clearly disclosing paid items where relevant.

## 2. Academy consistency and regression checks

Keep `courses.json` as the catalog source of truth. Before announcing free access, add/verify automated checks that:

- every catalog course has a unique ID and non-empty title;
- every stage points to an existing lesson file and stage IDs are unique and ordered;
- free/paid access flags agree with the store grant mapping;
- paid courses remain locked unless purchase/VIP entitlement is verified;
- `/academy`, `/courses`, lesson handlers, and Mini App render the same course title, lesson count, access status, and current progress;
- existing progress is preserved and completing a lesson twice cannot duplicate rewards;
- the displayed completion count never exceeds the actual number of valid stages.

Do not rewrite users' progress or grant paid access as part of a catalog sync. If legacy course IDs differ, report a migration plan first; never overwrite progress in production.

## 3. Opt-in feedback funnel

Existing handlers include `/bugreport <details>`, `/suggest <idea>`, and `/feedback <text>`. The explicit bug/suggestion handler persists entries in the canonical DB through `state_manager.atomic_update` and notifies the owner best-effort.

For a community launch, surface these commands in `/help`, the Academy and Mini App. Keep feedback voluntary, limit text length, rate-limit abuse, and explain what gets recorded. Never expose raw reports or usernames in public analytics.

Recommended first metrics (aggregate only):
- weekly active users and first-time starts;
- course opens, lesson starts/completions, and course completion rate;
- feature/command usage counts and command failure counts;
- feedback volume by category, response time, and unresolved count;
- Mini App load/auth failures.

Use event counters and short retention where possible. Avoid logging full message bodies, financial data, wallet addresses, or unnecessary personal identifiers. Clearly disclose analytics and give users a way to submit feedback without optional analytics.

## 4. Developer read-only audit route

Developer access should not imply owner access. Do not grant `/list_bugs`, broad filesystem reads, shell execution, production writes, user-list access, or financial permissions solely to enable code review.

Add a named, parameter-free audit intent or allowlisted report for:
- Academy catalog consistency (course IDs, lesson files, access flags; no user progress dump);
- governance/sociocracy code-path and test inventory (no individual ballots or voter identities);
- market-alert capability inventory (providers, supported symbols/markets, configuration-presence only; never expose tokens/API keys);
- command registry and collisions;
- aggregate analytics health.

Use the existing role/permission authority, log access decisions, bound output, and return `UNKNOWN/NOT_CONFIGURED` rather than infer integrations. No free-form `grep`/`find` or arbitrary `/app` paths.

## 5. Market alerts: do not overclaim

No claim that live stock/Nasdaq alerts work until the implementation, configured provider, symbols, freshness, error handling, and tests are verified. Separate crypto prices from stocks/index data. Report provider state and timestamp; label delayed or unavailable data explicitly. Do not offer investment advice or promise returns.

## 6. Suggested public launch copy (publish only after a release check)

> 🚀 **SLH Spark — קהילת האלפא פתוחה למשוב!**
>
> אנחנו מזמינים אתכם לנסות את כלי הלמידה והשירותים הזמינים ללא תשלום, במיוחד קורסי ביטקוין מאסטרי, טוקנים ב-AI, וממשל/תורת המשחקים. זמינות התכונות עשויה להשתנות, וחלק מהקורסים והמוצרים מוצעים בתשלום ב-Telegram Stars — המחיר ותנאי הגישה יוצגו לפני רכישה.
>
> מה כדאי לנו לשפר? שלחו `/suggest` עם רעיון או `/bugreport` לתקלה. המשוב שלכם יעזור לנו לתעדף לפי הצרכים האמיתיים של הקהילה.
>
> אנחנו מחפשים גם תורמים שרוצים לעזור בבדיקות, בתיעוד ובקוד דרך תהליך Pull Request מבוקר. גישה למפתחים אינה מעניקה גישה בלתי מוגבלת לשרת, למידע אישי או לפעולות כספיות.
>
> אין הבטחת זמינות לכל אינטגרציה; נתוני שוק והתראות יוצגו רק כאשר המקור והעדכניות מאומתים.

This is a draft, not a message that has been sent.

## 7. Release gates

Before merging or publishing:
1. Run Academy boundary, course access, feedback-handler, governance, and full regression tests.
2. Verify actual Mini App and bot output against the catalog.
3. Confirm the free-course list and paid-course disclosures match production.
4. Confirm aggregate analytics are privacy-conscious and opt-in where appropriate.
5. Confirm developer audit output reveals no personal, financial, or secret configuration.
6. Publish only after CI passes and an owner reviews the exact message.

## Explicit non-goals

- No price changes or free unlock of paid courses.
- No production database edits, rewards, or progress migration.
- No widening of developer permissions or shell/path access.
- No activation of stock/crypto providers, trading, BNB/TON deposits, or exchange gates.
- No announcement has been sent by this documentation PR.
