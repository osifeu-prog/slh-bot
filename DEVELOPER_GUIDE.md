# SLH OS Developer Guide
Generated: 08/04/2026 04:17:27

## Quick Start
1. Open PowerShell in: C:\Users\USER\slh-bot-clean
2. Run: python bot_gateway.py (for local testing - NOT for production)
3. Production bot runs on Railway (web service)

## Key Files
- bot_gateway.py: Main entry point (loads all handlers)
- handlers/loader.py: Loads all modules
- handlers/*.py: Individual command handlers
- state/db.json: Main database
- state/journal.json: System journal

## Useful Commands (in Telegram)
- /exec <cmd>: Run any shell command
- /dashboard: View system status
- /journal: Write to journal
- /admin: Admin panel
- /diagnose: Full system diagnostic

## Railway
- Service: web (eu-west)
- Start command: worker: python3 -B bot_gateway.py
- URL: web-production-22f28.up.railway.app

## Common Tasks
- Add new handler: Create handlers/new_feature.py, add to handlers/loader.py
- Deploy: git push (Railway auto-deploys)
- Check logs: railway logs --lines 50
