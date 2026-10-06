# SLH OS — TOMORROW HANDOFF
Date: 2026-10-07 (from session 2026-10-06)

## MISSION
Bot Shop — design + first implementation step.
NO ARCHITECTURE CHANGES WITHOUT WRITTEN PLAN.
ONE SOURCE OF TRUTH.
ONE TEST.
ONE FIX AT A TIME.

## MANTRA
OBSERVE → PROVE → FIX → TEST → FREEZE

## VERIFIED (2026-10-06)

### Bot / Runtime
- @SLH_Test_bot — mojibake fixed (61,688 → 0). Hebrew renders correctly.
- /help and /whoami added to admin_main.py, verified live.
- @SLH_Test_bot registered in Bot Vault (encrypted, identity match).
- @SLH_Wallet_bot registered in Bot Vault.
- Docker container slh-superadmin — running stable, health OK.
- /status, /admins, /guide, /tasks, /my_access working.

### Repo / CI
- Repo made public → GitHub Actions quota issue resolved.
- CI runs in 20-40s (previously 2-3s fails = quota exhausted).
- PR #424 (docs sync) MERGED.
- PR #425 (Trust Wallet smoke) MERGED.
- PR #426 (.gitignore cleanup) MERGED.
- PR #427 (Release Evidence fan-out) CLOSED (superseded by #428).
- PR #428 (deduplicate release evidence) MERGED.
- PR #429 (control plane CI contract) MERGED.
- PR #431 (wallet handoff retry-safe) MERGED.

### Security / Process
- gitleaks: 105 findings — 0 true secrets. All were SHA256 hashes + public BSC contract addresses.
- Branch ruleset "Protect main" ACTIVE:
  - deletion blocked
  - non_fast_forward blocked
  - linear history required
  - PR required (0 approvals)
  - status checks required: validate, full-regression, vault-regression
  - admin bypass: always
- gh CLI installed (2.62.0), authenticated as osifeu-prog.

### Infrastructure
- Railway: slh-os-control-plane / web ONLINE.
- Railway: slh-mcp ONLINE.
- web URL: https://web-production-22f28.up.railway.app
- Mini App: /mini-app-v4 → 200 OK
- Git: main @ 35e76bda, fully synced with origin.

## OPEN — PRIORITY ORDER

1. BOT SHOP — DESIGN SPEC (highest priority)
   Four decisions locked (2026-10-06):
     (1) Buyer:        both — existing users + external
     (2) Delivery:     combo — DIY template AND managed bot
     (3) Payment:      combo — Telegram Stars + Credits + BNB/TON
     (4) Location:     combo — @Me_ad_main_bot + dedicated bot + Mini App

   Existing infrastructure to reuse:
     - core/bot_factory.py        (10 functions: create, list, status, deploy, ...)
     - core/bot_registry.py       (DB-backed, secrets NEVER persisted)
     - handlers/stars_store.py    (/buystars <item_id>, Stars invoices)
     - store/stars_purchase_service.py
     - store/engine.py            (load_items, resolve_item_id)
     - store/items.json           (existing catalog: courses, hardware, plugins)

   Missing pieces to build:
     - store/items.json → add bot_template + bot_managed item types
     - handlers/bot_shop_handler.py → /bot_shop, /bot_buy <id>, /my_bots
     - grant flow: after payment → bot_registry.create_bot() + vault instructions
     - Mini App section: bot-shop (later)

   Questions still open:
     - Which templates to offer first? (shop, ledger, support, custom?)
     - Managed bot pricing model: monthly / one-time / revenue-share?
     - Where does the encrypted token get stored for managed bots? (Vault confirmed)
     - How does the buyer receive install instructions? (message / Mini App / doc link)

2. VERIFY @SLH_Test_bot end-to-end with second user
   - Test /help, /whoami, /status as a non-owner user
   - Confirm access control works as expected

3. MONITOR Release Evidence workflow for 24h
   - Confirm 1 success + N cancelled pattern holds
   - No true failures expected

4. PERSONAL ACCESS TOKEN — rotate for minimal scopes
   - Current token has ALL scopes (over-privileged)
   - Replace with: repo, workflow, read:org

5. CLEANUP: review remaining open branches
   - Many branches from past sessions
   - Not blocking, do when time allows

## STOP RULE
If a test fails:
STOP.
READ THE ERROR.
MAKE ONE SMALL FIX.
RUN THE SAME TEST AGAIN.

## DO NOT
- Do not run git filter-repo without a fresh clone + backup tag.
- Do not push directly to main without bypass awareness.
- Do not add secrets to any file in the repo.
- Do not merge PRs without green CI.
- Do not modify release-evidence.yml while CI is running.
- Do not paste bot tokens into any chat, issue, or commit.
- Do not delete the branch ruleset without an alternative protection.

## FIRST COMMAND TOMORROW
pwd
git status --short
git log -1 --oneline
gh run list --limit 5
railway status