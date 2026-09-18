# SLH Unified System Map

**Status:** approved federation model, implemented as a read-only Control Plane registry.

## Authority model

```
                         ┌──────────────────────────┐
                         │  SLH OS CENTRAL BOT      │
                         │  Control Plane           │
                         │  osifeu-prog/slh-bot     │
                         └────────────┬─────────────┘
                                      │
                     canonical state / economy / auth
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
   Flask API                    Telegram clients              Web / Mini App
   + Control Center             + AIR / future adapters       + Dashboard
        │                             │                             │
        └─────────────────────────────┼─────────────────────────────┘
                                      │
                         shared canonical services
                                      │
             Wallet Binding · Economy · Exchange · Academy
             Agents · Tasks · Marketplace · Payments · Staking
```

## External/legacy projects

These remain separately deployed until an explicit adapter is implemented:

- `SLH_investor_wallet_bot`
- `TELEGRAM-BOT`
- `slh-cloud-bot`
- `slh.co.il`

They are **not** treated as canonical state authorities.

## Current verified facts

- `bot_gateway.py` mounts the Flask `webapp.py` routes into the same gateway process.
- The gateway already exposes Control Center, Dashboard and API routes.
- `handlers.loader` loads exchange, wallet, payment, store, academy, staking, Alpha and many other modules into the central bot.
- BNB binding has challenge/verify/get-binding endpoints.
- `legacy_wallet_migration.py` records a verified wallet relationship only; it does not mint or credit balances.
- The internal SLH/CREDITS exchange has order placement and settlement logic.
- BNB deposit settlement currently handles native BNB, not BEP-20 token transfer events.
- Public Mini App staking mutations are intentionally disabled in the current webapp.

## Integration rule

All future clients should call the central API and read canonical state. A client adapter must not introduce a second balance ledger.

## Rollout order

1. Central registry + system map.
2. Health/readiness adapter for every client.
3. Identity/session adapter to central Telegram/Web auth.
4. Canonical wallet/economy adapter.
5. Product adapters: SaaS, Stores, NFT/Marketplace, Academy, Agents.
6. Legacy bot migration/redirects.
7. Mobile wrapper (Google Play / App Store) only after the unified API contract is stable.

## Important separation

The system map does **not** assert that every legacy feature is currently live. It distinguishes central modules that exist from external deployments that still require adapters. This prevents a UI from advertising a function before its backend settlement path exists.
