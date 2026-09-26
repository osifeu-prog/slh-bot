# SLH FAQ — Index

Canonical user-facing answers. Prefer these over free-form LLM guesses for money and wallet flows.

| Topic | File |
|-------|------|
| TON wallet verification (binding) | [TON_WALLET_VERIFICATION.md](./TON_WALLET_VERIFICATION.md) |
| Credits vs on-chain (short) | see TON file § after binding |

## Consumers

- **Human / Mini App** — link from wallet screen
- **`core/ask_router.py`** — intent `ton` returns a short answer from this pack
- **KYC** — not the same as wallet binding; no KYC module is wired here yet

## Rules

1. Never ask for seed / mnemonic in FAQ or bot replies.
2. `@wallet` (Telegram custodial) cannot complete TON Proof.
3. Binding is required before TON deposit credits.
