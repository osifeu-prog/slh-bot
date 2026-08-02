# SLH Railway Snapshot

Date:
2026-07-08


## Active Runtime

Project:
endearing-amazement

Service:
web

Role:
Main Telegram Runtime

Status:
ONLINE


## Telegram Issue

Error:
409 Conflict

Cause:
Multiple getUpdates consumers using same BOT_TOKEN


## Known Projects

- endearing-amazement
- slh-cloud-bot
- SLH_investor_wallet_bot
- nifti-bot
- TELEGRAM-BOT
- diligent-radiance
- slh-guardian
- Tax_Free_world_bot
- slh-api
- dazzling-unity


## Architecture Decision

Future:

Only SLH_GATEWAY owns Telegram polling.

Agents never call Telegram directly.


## Token History

Active token:
stored in Railway variables.

Old tokens found in backups.

Action:
Do not delete until migration complete.

