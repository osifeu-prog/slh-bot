# SLH OS v2.0

Complete automation platform controlled via Telegram.

## Features
- 45+ Telegram commands
- REST API with agents, tasks, health, stats, logs
- Web Dashboard (Agents, Tasks, Logs)
- Agent OS (create, state, inbox, permissions)
- Kernel + EventBus + TaskPlugin
- Marketplace Plugin Store
- Monetization (Free/Pro/Enterprise)
- Terminal Bridge (/exec, /termlog)
- Inspector & Master Agents (/inspect, /q, /watchdog)

## Quick Start
/start — Activate bot
/admin — Control panel
/exec <cmd> — Terminal access
http://localhost:8000 — Dashboard
http://localhost:5000/api/health — API status

## Architecture
- Telegram Bot (TeleBot)
- Flask API (REST)
- Web Dashboard (HTML/JS)
- SQLite/JSON Database
- Termux Daemon

## Deploy
Push to GitHub → Railway auto-deploys

## Status
✅ Production Ready
✅ Fully Tested
✅ 24/7 Operational
