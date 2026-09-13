# SLH Tokenomics — Current Baseline

**Effective date:** 2026-09-13
**Status:** Alpha-readiness baseline; not a promise of future yield, price, or liquidity.

## 1. Assets

| Asset | Role | On-chain | Transferable | Tradable | Current settlement |
|---|---|---:|---:|---:|---|
| Credits | Internal platform credit | No | Internal only | No | SLH OS economy service |
| SLH | Internal platform token | No | Yes | Yes | Internal exchange engine |
| TON | External asset | Yes | N/A | No in SLH OS | Deposit path only |
| BNB | External asset | Yes | N/A | No in SLH OS | Verified-wallet claim/deposit path |

## 2. SLH supply policy

SLH is **not minted by the Alpha economy path**. The current distribution authority transfers existing SLH balances and requires an event identifier with duplicate protection. Alpha must not claim a new supply, initial supply, or automatic minting mechanism unless a separately governed issuance policy is introduced.

## 3. Credits

Credits are internal accounting units. Current documented Stars packages are:

- 100 Telegram Stars → 100 Credits
- 450 Telegram Stars → 500 Credits
- 800 Telegram Stars → 1,000 Credits

Telegram Stars are the clearest current paid revenue path. The revenue ledger records **gross Stars**, not net cash proceeds after Telegram/platform fees.

## 4. Revenue accounting

Confirmed Stars payments are recorded through the Stars payment authority and, after successful economy application, an auditable revenue event is appended using an idempotent reference.

Internal Credit spending is **not** counted as external cash revenue.

The current production revenue ledger contains no historical events in the audited runtime snapshot. Therefore no historical revenue amount is asserted by this document.

## 5. Referral commission

Referral commission is an internal Credit allocation. It must not be treated as cash revenue and must not be described as externally funded until a treasury funding mechanism exists.

A production-safe treasury commission design requires an explicit treasury account/wallet, a defined funding source, atomic debit/credit semantics, and auditable reconciliation. No treasury address is invented by this document.

## 6. Staking

Staking uses internal Credits. It is not an on-chain investment product. Reward calculations currently operate in Credits and must not be marketed as guaranteed profit or externally funded yield until a funded reward pool/treasury policy is proven.

## 7. Exchange

The exchange engine supports reserve-based order matching and settlement between Credits and SLH. The audited production state currently contains no active `exchange_orders`, `exchange_trades`, `exchange_requests`, or `exchange_sequence` state.

Therefore Alpha UI must not claim that a live market currently has liquidity, active orders, or completed trades.

There is currently no platform trading fee defined. No fee rate is invented here.

## 8. Hardware

The current product metadata contains ESP32 hardware entries whose field name `price_usd` conflicts with `currency: ILS`. This metadata must be corrected before presenting those prices as an official purchase offer.

## 9. Alpha disclosure

Alpha should communicate clearly:

1. Credits are internal platform units.
2. SLH is an internal transferable/tradable token in the current system; it is not presented here as an on-chain asset.
3. TON and BNB are external assets with deposit/claim paths, not currently tradable assets inside the SLH exchange.
4. Revenue figures are only asserted when backed by the revenue ledger.
5. Staking rewards are Credits and are not a promise of profit.
6. No market liquidity, treasury balance, token price, or cash revenue is invented.

This document is a snapshot of the system's actual implemented boundaries as audited on 2026-09-13. Code and production state remain authoritative over examples in this document.
