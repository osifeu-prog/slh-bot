# SLH OS — Master Hub Architecture

## Objective
Converge the existing SLH ecosystem into one canonical control and product architecture.
Telegram is the primary human control surface during the transition; it is not the long-term system of record.

## Canonical layers
1. SLH Core: identity, authority, state/db.json, economy, revenue ledger, Academy, agents, wallet and settlement services, token/exchange services.
2. SLH API / Control Plane: authenticated API, system map, health, MCP bridge, and shared API surface for Telegram, web, Android and iOS.
3. Clients: Telegram MAIN bot, Mini App/web, future Android/iOS app.
4. Edge/acquisition bots: existing external Telegram bots; keep audience during migration, but connect verified telemetry before central counting.
5. Infrastructure/nodes: Railway, PC_Osif2 + SLH Agent, Ollama, website, monitoring, databases and queues.

## Bot federation contract
Each managed bot should have a canonical registry record with stable id, Telegram metadata, role, Railway binding, repository/branch, lifecycle state, telemetry state, last heartbeat, user-event source and revenue-event source.
Secrets such as Telegram BOT_TOKEN never belong in state/db.json.

## Central business model
Users are counted centrally only after a verified canonical event or canonical MAIN creation.
Revenue is counted only after authoritative external payment confirmation. Internal Credits spending is not cash revenue.
Acquisition traffic remains distinct from activated canonical users.

## Migration lifecycle
ACTIVE -> MIGRATION -> RETIRED
A bot is retired only after audience redirection, feature parity, user/revenue reconciliation, dependency migration, intentional polling shutdown, and archival.
No bot is auto-shutdown by the control plane.

## Mobile target
Android / iOS / Telegram / Web -> authenticated SLH API -> SLH Core -> canonical state.
This keeps business logic in one place and prevents duplication across clients.

## Current known nodes
- MAIN source: osifeu-prog/slh-bot
- Current production runtime under active work: Railway slh-cloud-bot
- Osifs_Factory_bot: live legacy acquisition bot, telemetry not yet connected
- slh-AI-bot: legacy/crashed, do not revive blindly
- slh-api: retained while legacy website/API paths depend on it
- PC_Osif2: Ollama qwen3:4b + SLH Agent

## Control surfaces
Telegram MAIN: /biz /biz_users [days] /biz_revenue [days] /biz_ai /biz_bots /admin /exec
PowerShell: slhpc slhbiz slhusers slhrevenue slhbots slhai slhsync

## Next consolidation step
Make all control surfaces read from one federated bot registry and verified telemetry contract. External bots are migrated one at a time.