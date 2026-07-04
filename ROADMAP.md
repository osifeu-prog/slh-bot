# SLH OS – Roadmap

## ✅ Completed (3 July 2026)
- Agent CRUD (create, list, send, inbox, state)
- Persistent storage (state/db.json + Railway Volume)
- /exec Python runner
- /demo with sample tasks & agents
- state_manager module
- tutor agent auto-reply (fallback)
- Start menu updated

## 🔜 Immediate Next
- [ ] Install Ollama in Dockerfile for /ask LLM
- [ ] tutor agent → full LLM integration
- [ ] Inline buttons for /start
- [ ] User onboarding flow (/join → /demo tasks)
- [ ] Health check endpoint (monitoring)

## 💰 Monetization (Phase 1)
- [ ] Telegram Stars for /ask usage
- [ ] Premium agents (paid via Stars)
- [ ] Course payments (USDT/Stars)
- [ ] Affiliate referral commissions

## 🏗 Architecture (Matala 2)
- [ ] State Manager → single source of truth
- [ ] Event Bus → decoupled components
- [ ] Control Plane → centralized orchestration
- [ ] Agent Heartbeat → health monitoring
- [ ] Dashboard → read-only system view


## 📅 Session Update — 4 July 2026

### ✅ Completed Today (9 real bugs found + fixed, all verified live)
- Fixed /journal_read sync issue (Volume vs git split)
- Fixed slh_dashboard.sh token KeyError + dangerous auto-start (409 risk)
- Fixed marketplace.json data-loss risk (moved to state/ Volume)
- Fixed critical /join crash (welcome_handler.py wrong db.json path)
- Removed dead duplicate handlers: /start, /demo, /logs, /refreshtoken
- Fixed /refreshtoken re-registering every reconnect loop (architecture risk)
- Fixed critical /refreshtoken crash (is_admin() wrong argument type)

### 🔴 Immediate Next (updated priority)
- [ ] Rebuild /admin menu from real 81-command list (split into /admin + /help)
- [ ] Wire up /balance + /buy (code already drafted, see journal 3-Jul)
- [ ] Verify myprogress_handler.py owns /myprogress (not dead code in learn_handlers.py)
- [ ] Decide fate of orphaned join_fix.py

### 💰 Monetization — updated priority order
1. /balance, /buy (code ready, not yet wired in)
2. Telegram Stars (fastest real payment path)
3. TON payment verification via toncenter.com API (currently manual hash-check only)
4. Automate referral commissions (85% promised, not yet automated on payment)

### ⚠️ Working Rules Learned Today (critical - prevents stuck sessions)
- NEVER use /tmp in Termux (no write permission)
- NEVER paste long text blocks (100+ lines) in one go - causes truncation/hangs
- NEVER use python3 -c "..." with long strings - use heredoc (<< 'TAG') instead
- State files (journal.json, db.json, marketplace.json) live SEPARATELY on
  Termux (git-synced) and Railway Volume (NOT auto-synced by git push) -
  code changes deploy automatically via git push, but state file changes
  need explicit /exec sync to Railway
- Always pull live db.json via /exec before local DB work (local copy drifts stale)


## 📅 Session Update — 4 July 2026, Part 2 (parallel work discovered)

### ✅ Economic Engine LIVE (verified working in production)
- /balance — shows real credit balance from db.json
- /buy <item> — deducts credits, grants item (ask_credit=10cr, premium_agent=50cr)
- /giveme — admin-only, adds 50 credits (for testing/manual grants)
- econ_handler.py — clean separate module, wired into bot_stable.py
- CONFIRMED LIVE: tested /balance (170 credits) and /buy ask_credit
  (correctly deducted to 160) - real DB writes, not simulated

### 🔴 Still needed for REAL money (not just internal credits)
- [ ] Connect credits to real payment: Telegram Stars or TON purchase
      (currently credits only enter system via admin /giveme - no
      real payment path exists yet)
- [ ] Wire referral commissions in /buy (85% to referrer - promised in
      /referral text, not yet automated)
- [ ] Rebuild /admin menu from real 81-command list (still pending,
      original goal from this session, not yet done)

### 🟡 Also discovered - parallel cleanup in progress
- Large untracked archive/ cleanup happening (bot.py, bot_test.py,
  run.py, minimal_bot.py etc moved to archive/) - not yet committed
- New untracked files appearing: core/command_router.py,
  core/bootstrap_commands.py, state/token_loader.py - possible
  larger refactor starting, needs review before committing
- admin_utils.py created (new) - houses is_admin() to avoid circular
  imports, referenced by econ_handler.py giveme command


## 🎯 NEXT SESSION — START HERE
1. **Rebuild /admin menu** from the real 81-command list (this was
   the ORIGINAL goal of the 4-Jul session, still not done — everything
   else was bugs discovered along the way). Split into /admin (system/
   agents/voting/revenue) and /help (learning/courses/referral/demo).
   Full command list already gathered - see "Immediate Next" section above.
2. Then continue down the priority list below.
