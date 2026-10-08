# SLH OS API Reference

This reference matches the current Flask HTTP surface in `webapp.py`.
Telegram bot commands and Telegram Mini App callbacks are separate surfaces.

## Production

Base URL:

`https://slh-cloud-bot-production.up.railway.app`

The Mini App is served by the same production service. There is no separate end-user Dashboard/API host.

## Authentication boundaries

- User-scoped APIs use server-side Telegram Mini App `initData` validation via `X-Telegram-Init-Data`.
- Wallet handoff sessions are accepted only by wallet-scoped API paths; they are not general Mini App authentication.
- Developer Lab endpoints require the Developer Lab token plus an authenticated actor UID with an allowed role.
- Sensitive runtime state, secrets, and unrestricted shell access are not exposed through the public HTTP API.
- Settlement readiness is governed by the canonical BNB/TON gate and authority layers; this document does not imply that an external settlement gate is open.

## Core endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Service health check |
| `/api/ai/chat` | POST, OPTIONS | Canonical public AI intake; Telegram identity is used when valid initData is supplied |
| `/api/v1/ai/readiness` | GET | AI readiness read model |
| `/api/public/site-status` | GET, OPTIONS | Public aggregate SLH OS truth beacon for `slh-nft.com` / `slh.co.il`; no user balances, secrets, or mutation controls |
| `/api/v1/me` | GET | Authenticated investor/user snapshot |
| `/api/v1/system/unified-map` | GET | Unified system map read model |
| `/api/v1/financial-truth` | GET | Unified financial truth |
| `/api/v1/stars/financial-truth` | GET | Telegram Stars financial truth |
| `/api/v1/governance` | GET | Governance read model |
| `/api/v1/vault` | GET | Bot Vault read model |
| `/api/v1/growth-hub` | GET | Growth/referral hub read model |
| `/api/v1/growth-events` | POST | Growth event intake |
| `/api/v1/settings` | GET, POST | User UI settings |
| `/api/v1/store` | GET | Store/catalog read model |
| `/api/v1/card/store` | GET | Card purchase catalog |
| `/api/v1/stars/invoice` | POST | Build/create a Stars invoice request |

## Wallet and settlement endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/wallet/bnb/handoff` | POST | Create wallet-scoped BNB browser handoff |
| `/api/v1/wallet/bnb/browser-quick-return` | GET | BNB browser return configuration |
| `/api/v1/wallet/bnb/browser-quick-return/verify` | POST | Verify browser-side BNB return intent |
| `/api/v1/control/wallet-health` | GET | Wallet control/readiness status |
| `/api/v1/control/ton-go-live` | GET | Canonical TON go-live read model |
| `/wallet-handoff` | GET | Wallet handoff landing page |
| `/wallet-connect` | GET | WalletConnect landing page |
| `/api/walletconnect/config` | GET | WalletConnect configuration |
| `/slh-browser-send` | GET | External browser SLH send page |
| `/slh-smoke` | GET | SLH browser smoke/test page |
| `/bnb-browser-return` | GET | BNB browser return page |
| `/bnb-smoke` | GET | BNB smoke/test page |
| `/tonconnect-manifest.json` | GET | TON Connect manifest |

External settlement remains governed by its own runtime gates. BNB is not implicitly opened by any endpoint listed here.

## Exchange, tasks, staking and journal

| Endpoint | Method | Purpose |
|---|---|---|
| `/market` | GET | Market/trading page |
| `/api/v1/tasks` | GET | User task read model |
| `/api/v1/tasks/<task_id>/complete` | POST | Complete a user task |
| `/api/v1/journal` | GET, POST | User journal read/write |
| `/api/v1/staking` | POST | Create staking position |
| `/api/v1/staking/positions` | GET | List staking positions |
| `/api/v1/staking/unstake` | POST | Unstake a position |
| `/api/v1/staking/revenue-share/status` | GET | Staking revenue-share status |
| `/api/v1/staking/revenue-share/distribute` | POST | Distribute governed staking revenue share |

The Internal Exchange is a Telegram/Mini App business surface backed by the canonical exchange read model; it is distinct from external BNB settlement and an on-chain DEX.

## Payments

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/card-pay/checkout` | POST | Start card checkout |
| `/api/card-pay/callback` | POST | Payment provider callback |
| `/card-pay/success` | GET | Card payment success page |
| `/card-pay/failure` | GET | Card payment failure page |
| `/card-pay/cancel` | GET | Card payment cancellation page |

## Developer Lab

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/dev/lab/propose` | POST | Submit a governed developer proposal |
| `/api/dev/lab/file` | GET | Read an allowed project file |
| `/api/dev/lab/requests` | GET | List pending developer requests |
| `/api/dev/lab/preview/<request_id>` | GET | Preview a proposal |
| `/api/dev/lab/status/<request_id>` | GET | Read proposal status |
| `/api/dev/lab/approve/<request_id>` | POST | Owner approval path |
| `/api/dev/lab/reject/<request_id>` | POST | Owner rejection path |
| `/api/dev/lab/ci/<request_id>` | GET | Read CI status for a proposal |

Developer Lab access is intentionally separate from the public user API and remains governed by role/authority checks.

## Mini App and UI entry points

| Endpoint | Method | Purpose |
|---|---|---|
| `/mini-app` | GET | Mini App entry |
| `/mini-app-v2` | GET | Mini App compatibility entry |
| `/mini-app-v3` | GET | Mini App compatibility entry |
| `/mini-app-v4` | GET | Current Mini App UI entry |

## Notes

- `state/db.json` remains the canonical runtime source of truth.
- Read models should be preferred over ad-hoc database reads.
- Runtime writes must flow through the existing authority/economy services and governed deployment path.
- This reference covers Flask HTTP routes only; it intentionally does not replace the Telegram command inventory.
