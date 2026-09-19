# SLH Control Plane — Persistent Handoff
Snapshot: 2026-09-19

## Mission
SLH OS is intended to be one usable production system where ordinary users can build complex projects composed of microservices, servers, agents, bots, APIs and workflows. Website, Mini App, Telegram bots and Control Plane must share one canonical architecture, with persistent documentation so new sessions can resume without reconstructing history.

## Canonical production
- Repo: `osifeu-prog/slh-bot`, branch `main`
- Railway project: `endearing-amazement` (`fd30fefb-3d35-48a5-a7cb-e05337e812c4`)
- Service: `web`
- Production environment: `661caa13-83cb-4197-8825-943bebf96c5a`
- Start: `bash start_railway.sh`
- Latest verified deployment: `7ee7af82-f27c-4a48-930f-83aa744a1806` SUCCESS
- State: `state/db.json` MASTER; `state/agents.json` CACHE

## Website
Railway project `diligent-radiance` (`97070988-27f9-4e0f-b76c-a75b5a7c9673`), production `e0a8a279-4dc2-4461-8ba6-d16594d6ceca`.
- Service `SLH.co.il`: `63471580-d05a-41fc-a7bb-d90ac488abfd`
- Repo `osifeu-prog/SLH.co.il`, branch `main`
- Serves `docs/` directly: `python -m http.server 8080 --directory docs`
- Domains: `slh.co.il`, `slh-nft.com`
- Latest known deployment SUCCESS (2026-09-16)
- Inspect `docs/` first; do not assume root frontend.

## Website AI contract
Historical project evidence confirms the intended website assistant path:
- `js/ai-assistant.js` → `POST /api/ai/chat`
- canonical API documented as `https://slh-api-production.up.railway.app/api/ai/chat`
- frontend should not contain provider API keys
- existing integration also documents Telegram auth, bot↔website sync and analytics
Do not create a second AI backend merely because the Telegram AI bot is down.

## AI bot — current blocker
- Service: `slh-AI-bot` id `06b914f7-3e5f-4d35-82b2-5efd80fdca6a`
- Repo: `osifeu-prog/slh-claude-bot`, branch `main`, root `/slh-claude-bot`
- Domain: `slh-ai-bot-production.up.railway.app`
- Code identifies as `@SLH_Claude_bot` / “SLH Spark AI”
- It uses Free Unlimited Groq/Gemini mode
- Latest deployment: `8ce3b2f4-5ec1-4848-b0ff-3c65a1b63ec0` CRASHED
- Verified root cause: `aiogram.exceptions.TelegramUnauthorizedError: Telegram server says - Unauthorized` at `await bot.get_me()`
- `shared.coordination not loadable: No module named 'shared'` is a warning, not the crash root cause.

Repair rule: identify the canonical Telegram identity first; then update only the correct Railway secret. Never copy a token from another bot, never expose token values, and never create another AI bot.

## Bot Factory
- Service: `Osifs_Factory_bot`, id `78503f9f-1db4-4d54-a74d-a005472dc7e3`
- Current live/green from prior checks
- Intended role: create/configure/connect bots, health, logs, ownership
- Do not delete/merge until source and ownership mapping is verified
- Must not create unmanaged duplicate runtimes

## API
- Canonical API repo: `osifeu-prog/slh-api`, branch `master`
- Railway domain: `slh-api-production.up.railway.app`
- Preferred backend for website AI unless live source inspection proves a newer canonical route

## Legacy candidate
- `slh-fastapi` id `36269107-908a-449f-97ba-787871ba322f`
- Domain `slh-fastapi-production.up.railway.app`, port 8000
- Latest known deployment FAILED (2026-06-21)
- Contains many legacy-looking token/admin/JWT/provider variables
- Do not redeploy/delete blindly. First search live website/Mini App references. Remove only after dependency evidence.

## Other important Railway services in diligent-radiance
- TON-MNH-bot — live
- monitor.slh — live
- Postgres — live
- Redis — live
- SLH.co.il — live
- Osifs_Factory_bot — live
- slh-AI-bot — crashed on Telegram authorization
- slh-fastapi — failed/legacy candidate

## Duplicate runtime
Railway project `slh-cloud-bot`, service id `48b829d9-7bec-4d6e-ac25-025c77ce2794`, uses `osifeu-prog/slh-bot` main with `python3 -u -B bot_gateway.py`. Verify Telegram identity/purpose/ownership before changes.

## Product target: AI for everyone
A simple/free user must be able to ask for complex work and have the system guide and execute a project composed of agents, microservices, servers, bots and APIs without understanding the backend.

Required architecture:
1. One canonical AI intake.
2. Persistent user/session/project context.
3. Safe planner/orchestrator.
4. Project workspace and service graph.
5. Controlled provisioning tools for agents/services.
6. Health, logs and ownership surfaced in Control Plane.
7. Human escalation for destructive, financial, credential-sensitive or ambiguous actions.
8. Every completed change recorded in the persistent journal/handoff.

## UX target
- Gateway Hero: “מי אתה ומה אתה מחפש?”
- Simple: welcome → wallet → first purchase → community/main bot
- Advanced: live status, neural data, quick commands, terminal, contracts, feed
- Navigation: Start / Wallet / Bots / Earn / Guides / Community
- Ctrl+K command palette
- Dynamic permission/usage-aware navigation
- Friendly errors and progressive disclosure
- Reuse existing Assistant/Selha infrastructure; no duplicate support bot
- Support: user → Website/Main Bot → SLH Assistant → guide/troubleshoot/action → ticket → human/admin

## GitHub access limitation
Current connector can write `osifeu-prog/slh-bot` but cannot write `osifeu-prog/SLH.co.il`; branch creation there returns 403 Resource not accessible by integration even after branch protection was disabled and GitHub was reconnected. Do not repeatedly retest. Codex is currently usage-limited; continue through active tools.

## Completed production fixes
1. `/logs` collision fixed in `handlers/audit_handler.py`; commit `e34d2d8b740b1884f9b7c9e72ae8f58d992d9980`; deployment `eba0df55-027d-4a32-864a-940096d2816b` SUCCESS.
2. `/esp` Markdown/duplicate garbled block fixed; commit `b1c781bd149e23532603b496378b1f1f73cbdb1d`; canonical deployment `7ee7af82-f27c-4a48-930f-83aa744a1806` SUCCESS.
3. Economy hardening includes P2P transfer idempotency, TON concurrency protection, BNB claim idempotency, staking gates and marketplace checks.

## Token-balance safety
Do not mint, burn, redistribute, import or manually modify `wallet.token_balance` until provenance is established. Forensic evidence: `state/exec_audit.json` entry index 6524 contains a direct Python assignment to owner/UID501 token balances around the unexplained 2026-09-11 creation event. Historical snapshots had zero balances. Treat current balances as evidence, not a correction target.

## Alpha
Order: Economy sanity → Alpha flag → smoke test → GO. User phrase: “פתח את Alpha”. Unrelated non-critical ESP/legacy/UI work must not repeatedly block Alpha.

## ESP safety
Historical firmware uses HTTPS against the canonical API for claim/heartbeat/wallet/commands. Physical firmware/device state in Sep 2026 is unknown. Never invoke OTA until hardware, firmware version and device identity are known.

## Control Plane progress (2026-09-19)
- Added `core/project_context.py` as a read-only composition layer over existing agent, runtime, Railway and deployment authorities; it does not create a second state authority.
- Added `handlers/project_handler.py` and loaded it from `handlers/loader.py` as `/project` for an owner-scoped project graph.
- `core/ask_router.py` now attaches a minimal safe canonical project context to AI sessions (`project_id`, agent count, service count, runtime state).
- `SLH_GATEWAY.py` now routes read-only `status` through the canonical Project Context while retaining legacy module routing for compatibility.
- `handlers/health_monitor_handler.py` no longer uses hard-coded user balances/service counts; it reads canonical DB/runtime/Control Plane signals.
- Current latest code commit: `54885f8897e447341723db71d1c2bc8aea824948`.
- Railway created deployments for these commits but the latest code deployment is `NEEDS_APPROVAL`; do not report these changes as production-live until a `SUCCESS` deployment is verified.

## Immediate execution queue
### P0 — restore usable free AI
1. Establish canonical Telegram identity for the AI user intake.
2. Verify correct Railway secret ownership without exposing values.
3. Repair `slh-AI-bot`.
4. Verify `get_me`, continuous runtime, Groq/Gemini fallback, session persistence and a real free-user conversation.
5. Verify website `/api/ai/chat` independently.

### P0 — website/backend
6. Inspect `SLH.co.il/docs` through a working repo access path.
7. Map all AI/auth/API references.
8. Consolidate verified paths onto canonical `slh-api`.
9. Verify Mini App integration; preserve protected files unless a concrete defect requires change.

### P1 — Factory
10. Inspect Factory source/logs/commands.
11. Map create/configure/connect/health/log/ownership to Control Plane.
12. Prevent unmanaged duplicate bots/runtimes.

### P1 — legacy/duplicates
13. Search live site/Mini App references to `slh-fastapi-production.up.railway.app`.
14. Mark legacy and remove stale user-facing references after dependency proof; do not delete before proof.
15. Audit `slh-cloud-bot` ownership/identity.

### P1 — product
16. Finish Simple/Advanced navigation and Gateway Hero.
17. Make AI assistant persistent and project-aware.
18. Expose authorized Control Plane health/project graph.
19. Give every important bot a canonical registry: purpose, owner, source, deployment, health.
20. Persist every major session handoff here.

## New-session bootstrap
Start with:
“פתח את `docs/SLH_CONTROL_PLANE_HANDOFF.md` מה-repo הקנוני והמשך מה-Immediate execution queue. בדוק live state קודם, בצע את הפעולה הבאה, אמת production ותעד את התוצאה. אל תחזור על שאלות שכבר נפתרו.”

## Hard rules
- Never expose secrets/tokens/API keys/JWT/admin credentials.
- Never alter token balances without provenance and explicit authorization.
- Never create duplicate AI/support layers.
- Never claim success without live verification.
- Never delete services before ownership/dependency evidence.
- Never OTA ESP before physical identity/firmware is known.
- Do not freeze the project because a non-critical subsystem is imperfect.
- Prefer one canonical path over competing runtimes.
- Record material changes with date, component, result, commit/deployment and remaining work.
