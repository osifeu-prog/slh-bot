# SLH OS — Mobile-First Handoff

Updated: 2026-09-29

## Current main

`e3919ab31eddb1a05652195ab1c792fa8a2bb0cb`

PR #284 is merged.

GitHub checks on main/e3919ab3:
- SLH CI: PASS
- SLH Full Regression: PASS
- Bot Vault Regression: PASS

## Railway production

Project:
`slh-os-control-plane`

Environment:
`production`

Canonical services:
- `web`
- `slh-mcp`

Latest validated deployments:
- web: `1008b6f3-b037-469d-8f0b-b236842ee17f` — SUCCESS
- slh-mcp: `707f9d00-dced-4049-8312-faa3b7ebfd06` — SUCCESS

Web health:
`/health = 200`

Web runtime:
- RUN_BOT=1
- authenticated MQTT listener active
- BSC treasury snapshot available
- one canonical web replica

## Telegram blocker

The environment `BOT_TOKEN` is rejected by Telegram with HTTP 401.

PR #284 added a safe encrypted Bot Vault fallback for `@Me_ad_main_bot`, but production logs currently show:

`[TELEGRAM] Bot Vault fallback unavailable: ValueError`

followed by:

`BOT_TOKEN rejected by Telegram; trying Bot Vault fallback`

and then 0 Telegram bots running.

No 409 duplicate-polling conflict was observed.

Next action:
Verify that the production Bot Vault contains an encrypted entry for `@Me_ad_main_bot` and that `SLH_VAULT_KEY` is valid. Do not paste or expose the token. If the vault entry is absent, use the operator-terminal rotation flow with a newly issued BotFather token.

## Important safety boundaries

Do not:
- enable BNB settlement automatically
- enable TON settlement automatically
- mint/burn synthetic SLH
- bypass wallet ownership binding
- bypass Telegram Mini App authentication
- start a second Telegram polling instance
- revive `slh-AI-bot` or `slh-fastapi` blindly

Canonical wallet semantics:
- token_balance = total ownership
- live_token_balance = spendable ownership
- exchange_reserved_slh = escrow

Reserve 40 from 100:
100 total / 60 live / 40 reserve

## AI usability

Known problem:
old AI router rejected inputs over 1500 characters.

This mobile-first branch changes the canonical AI limit to 4096 and updates the web intake to the same boundary.

It also changes the fallback Mini App URL to:
`https://web-production-22f28.up.railway.app/mini-app`

The security model remains unchanged:
- Telegram initData is server-validated when provided.
- client-supplied user_id is never trusted for authorization.

## Broadcast

Owner-only `/broadcast <text>` exists.

The handler has been hardened to:
- reject empty/oversized messages
- keep the owner-only gate
- continue when one recipient fails
- report sent/failed counts
- add a small send delay

Do not send the Alpha broadcast until Telegram polling is confirmed healthy.

Suggested broadcast text:

🚀 SLH OS ALPHA IS LIVE

Smart Layer Hub is opening its next Alpha wave.

🤖 AI assistant
🎓 Academy
👛 Wallet & Credits
📊 Dashboard / Mini App
📈 SLH trading terminal
🎯 Missions & rewards

פתחו את /miniapp או /trade כדי להתחיל.

ה־Alpha מתמקד במסחר ובשימוש במערכת; מסלולי BNB/TON settlement נשארים מאחורי אימות on-chain ייעודי.

## Local synchronization

Use only the clean verification checkout:

`/mnt/c/Users/USER/slh-bot-main-verify-20260928`

Commands:

```bash
cd /mnt/c/Users/USER/slh-bot-main-verify-20260928
git fetch origin main
git reset --hard origin/main
git status --short
git log -3 --oneline
```

Expected main:
`e3919ab3` until PR #285 is merged.

## Current open work

PR #285:
`fix/mobile-first-ai-broadcast-20260929`

Purpose:
- AI input boundary 4096
- canonical Mini App URL
- safer broadcast loop
- canonical Railway registry name
- deploy workflow aligned with actual Railway project
- Bot Vault identity lookup improvements
- mobile handoff documentation

Do not merge PR #285 until:
1. SLH CI passes
2. Full Regression passes
3. Runner Smoke passes
4. Bot Vault Regression passes

Then deploy to Railway and verify runtime.

## Tomorrow's final sequence

1. Verify PR #285 checks.
2. Merge PR #285 if all green.
3. Deploy main to canonical Railway web.
4. Verify Telegram polling.
5. Run `/vault_health @Me_ad_main_bot`.
6. Verify Mini App opens from Telegram and auth succeeds.
7. Verify AI accepts >1500 chars.
8. Verify `/trade`, `/orders`, buy/sell/cancel using internal SLH/Credits semantics.
9. Send the Alpha broadcast.
10. Keep BNB/TON settlement gated until deliberate production on-chain verification.
11. After production is stable, build store-packaging layer for Google Play/App Store.

Goal:
Reach a state where normal operator work can be done from Telegram/control-plane, with desktop needed only for exceptional deployment/auth/credential tasks.
