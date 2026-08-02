# SLH Service Ownership Map

Generated:
2026-07-08


## Rule

No service may call Telegram getUpdates directly
except the official SLH Telegram Gateway.


---

## Production

### endearing-amazement
Service:
web

Role:
Main Telegram Runtime

Current:
ONLINE

Known issue:
409 Conflict


---

## API Layer

### slh-api

Role:
Backend API

Dependencies:
Redis
PostgreSQL


---

## Agents

### slh-guardian

Role:
Security / Guardian Agent


### Tax_Free_world_bot

Role:
Economic Agent


---

## Legacy Systems

### SLH_investor_wallet_bot

Status:
Legacy

Potential reuse:
Wallet logic


### nifti-bot

Status:
Legacy


### TELEGRAM-BOT

Status:
Legacy


---

## Websites

### slh.co.il

Role:
Public Web Presence


---

## Future Architecture

Telegram
    |
    v

SLH_GATEWAY

    |
    +-- EventBus
    |
    +-- Agents
    |
    +-- LLM Controller
    |
    +-- CRM
    |
    +-- Economy


