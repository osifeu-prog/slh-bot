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
