# SLH Team Handoff — 2026-09-14

## Mission

Restore and stabilize the SLH ecosystem without creating a second source of truth. Work in this order:

1. Money paths and economy safety
2. Runtime / Railway / Telegram recovery
3. Website + Mini App integration
4. Agent / Control Plane reliability
5. ESP protocol hardening
6. UX polish and Post-Alpha work in parallel

## Non-negotiable security boundary

ESP hardware is owner-only at this stage.

The developer may inspect and modify repository-side ESP integration code only after review, but must not receive physical/device credentials or operate, flash, provision, or remotely control the user's ESP devices.

Do not expose secrets, wallet keys, bot tokens, MQTT credentials, or Railway variable values in tickets, commits, screenshots, or chat.

## Current source-of-truth model

- `state/db.json` is the canonical application/economy state boundary.
- `state/agents.json` is a cache/derived registry, not an independent economy authority.
- Railway production `web` is the current deployed gateway/API runtime for `osifeu-prog/slh-bot`.
- Avoid creating parallel production runtimes or duplicate Telegram polling instances.

## Runtime topology

GitHub `osifeu-prog/slh-bot`
→ Railway production `endearing-amazement / web`
→ `bot_gateway.py`
→ Telegram polling + Flask API
→ WebApp / Mini App + economy + agents + ESP integration

There is also a historical/secondary Railway project named `slh-cloud-bot`. Treat it as a duplicate/secondary runtime unless explicitly re-authorized. Never start a second polling instance for the same Telegram bot token.

## Money-first audit matrix

For every money path verify:

- authentication
- authorization
- source of truth
- atomic state mutation
- idempotency key/event ID
- ledger/audit record
- retry behavior
- failure behavior
- user-visible result

Required paths:

`Buy → Payment → Credits → SLH → Transfer → Stake → Reward → Deposit → On-chain settlement`

Do not invent a new payment or minting mechanism to compensate for an unclear existing path.

## Known implemented boundaries

- Telegram Stars payment authority exists.
- Internal SLH distribution has an explicit event ID and atomic/idempotent boundary.
- P2P transfer has duplicate protection.
- Mini App authentication validates Telegram init data server-side.
- Mini App staking is authenticated and user-scoped.
- Governance was canonicalized to `state/db.json` in the merged codebase.
- Alpha control plane is owner-gated and deterministic in code.

## Known open items

### 🔴 ESP Wallet Sync protocol

The server currently has an ESP `sync` action, but the current firmware command handler implements `ping`, `status`, `refresh`, and `screen` commands rather than wallet synchronization. Do not pretend server-side `sync` is a working ledger protocol.

Design target: a bounded/versioned payload plus explicit device ACK, with no independent monetary authority on the device until the protocol is proven.

The firmware MQTT buffer is limited; future sync payloads must remain bounded or be explicitly chunked.

### 🟠 ESP device identity cleanup

There are historically duplicated IDs for the same hardware MAC. Do not delete or rewrite registry entries until ownership, heartbeat history, and topic mapping are reconciled.

### 🟠 Telegram groups

Determine whether missing group responses are caused by Telegram delivery/privacy/permissions or by handler routing. Do not assume privacy mode is the root cause without live update evidence.

### 🟠 Website

The separate `osifeu-prog/SLH.co.il` repository exists and is public, but its current `index.html` contains garbled Hebrew text and legacy package copy. It is not the same artifact as the private `slh-bot` runtime. Do not silently replace it from the bot dashboard.

### 🟠 Mini App UX

Current Mini App has duplicated navigation and too many first-level actions. Consolidate toward a simple user model: Home / Wallet / Learn / Market / Account, while keeping admin/control-plane functions out of normal user navigation.

## Change policy

For every change:

`root-cause evidence → smallest safe change → tests → review → deploy → runtime verification`

No manual production DB edits. No secrets in source. No direct ESP access for non-owner users.

## Alpha policy

Classify findings as:

- 🟢 proven
- 🟠 verification/hardening
- 🔴 actual blocker

Do not turn Post-Alpha work into an Alpha stop condition unless that capability is explicitly part of the Alpha promise.
