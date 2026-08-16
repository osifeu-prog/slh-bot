# SLH Railway Ecosystem Map

Generated: 2026-07-08

## Production Runtime

### endearing-amazement
- Service: web
- Role: Main Telegram Runtime
- Status: Online


## Infrastructure

### slh-api
- FastAPI backend
- Redis
- PostgreSQL


## Agents

### slh-guardian
- Guardian system

### Tax_Free_world_bot
- TAX_FREE agent


## Legacy Systems

### SLH_investor_wallet_bot
### nifti-bot
### TELEGRAM-BOT


## Websites

### slh.co.il
### monitor.slh.co.il


## Known Issue

Telegram getUpdates 409 conflict detected.

Cause:
Multiple Telegram pollers using same BOT_TOKEN.

Investigation required:
Find active consumer of main token.
