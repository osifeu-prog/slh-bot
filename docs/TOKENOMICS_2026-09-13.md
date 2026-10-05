# SLH OS — Canonical Tokenomics Baseline
**Effective date:** 2026-10-06  
**Status:** Current implementation baseline for SLH OS / Alpha.  
**Authority:** Runtime code + canonical state + live on-chain verification. Historical planning documents are not runtime authority.

## 1. The important distinction

SLH OS currently has **two internal economic units with different roles**:

| Unit | Nature | Main role |
|---|---|---|
| **Credits** | Internal accounting unit | Purchases, staking, rewards and the quote side of the internal SLH exchange |
| **SLH** | On-chain BSC token + internal SLH ledger | Token distribution, internal transfer/trading, and verified on-chain deposit/withdrawal flows |

Therefore **Credits are not currently the same thing as SLH**. The codebase contains separate balances and separate authorities for them. Merging them would require an explicit economic migration across purchases, rewards, staking, transfers, exchange, settlement and historical balances; it is not safe to do as a nomenclature change.

## 2. SLH — on-chain and internal layers

The deployed SLH token is a BEP-20 token on BNB Smart Chain:

- Chain ID: **56**
- Contract: `0xACb0A09414CEA1C879c67bB7A877E4e19480f022`
- Decimals: **15**

The SLH OS runtime also maintains internal SLH fields such as `token_balance`, `live_token_balance` and exchange reserve state. These internal balances are used by the SLH exchange/distribution authorities and are **not automatically identical to an external wallet's live on-chain SLH balance**.

The canonical SLH deposit service only increases an internal SLH balance after verifying the real BSC transaction, token contract, Treasury recipient, Transfer event, sender binding and confirmation threshold.

### Minting statement

The Alpha/SLH OS distribution path does **not** expose a mint operation; its policy is existing-balance distribution only.

That statement must **not** be expanded into “the deployed token contract is non-mintable.” External verification of the deployed contract shows a `mint` function and a mintable contract configuration, so contract-level supply authority must be treated as a separate smart-contract governance fact and verified on-chain before making supply guarantees.

## 3. Credits

Credits are internal accounting units.

They are used for:

- product purchases;
- staking;
- rewards;
- internal P2P transfers;
- the quote side of the SLH exchange.

Credits are **transferable internally**. They are not an on-chain asset and are not themselves the traded asset in the SLH exchange.

Internal Credit spending is not external cash revenue.

## 4. Telegram Stars pricing

The current canonical Stars pricing authority is:

| Stars | Credits | Bonus |
|---:|---:|---:|
| 100 | 100 | 0% |
| 500 | 550 | 10% |
| 1000 | 1200 | 20% |

VIP monthly subscription: **499 Stars**.

These values come from `core/stars_price_authority.py`. Historical documents containing `450 Stars → 500 Credits` or `800 Stars → 1000 Credits` are stale and must not be used as current pricing.

Stars are recorded as `XTR` and are external payment revenue; Credits granted from those payments are internal accounting units.

## 5. BNB settlement

BNB is an external BSC asset.

Current BNB settlement policy in SLH OS:

**1 BNB = 1000 Credits**

The settlement path is wallet-bound and verification-first. It checks BSC chain identity, transaction success, Treasury recipient, required confirmations and sender-to-bound-wallet equality, then performs an idempotent Credits ledger mutation.

BNB settlement does **not** create SLH.

The public BNB gate remains closed until the empirical settlement reconciliation is proven.

## 6. TON settlement

TON is an external on-chain asset.

The current runtime safety band is:

**100–110 Credits per TON**

The exact active rate is configuration-controlled and must be read from runtime state before being presented as a live quote.

TON settlement does **not** create SLH.

## 7. SLH Exchange

The internal exchange is:

**SLH / Credits**

SLH is the traded asset. Credits are the quote/accounting side.

The exchange engine maintains SLH reserves and Credit reserves atomically. No supply is created by a match.

A live market must not be advertised as liquid or active unless real order/trade state exists.

## 8. Rewards and referral

Current implemented referral reward:

- 0.9 Credits per successful referral
- 10 Points per successful referral
- 5 successful referrals can unlock one VIP month while the documented launch offer is open

The expired September 11, 2026 Holiday campaign is historical only; it does not constitute a current automatic SLH issuance path.

## 9. Staking

Current SLH OS staking operates on **Credits**, not on the external BSC SLH token.

Therefore statements such as “SLH staking” or “SLH revenue-share staking” must not be presented as current runtime facts unless a separate governed on-chain staking implementation is introduced.

## 10. Supply and backing

SLH OS must not invent:

- total supply;
- circulating supply;
- Treasury value;
- market price;
- liquidity;
- cash revenue.

Where an internal SLH balance is backed by a verified on-chain deposit, the backing event must remain auditable through the canonical transaction/event evidence.

## 11. Source-of-truth rules

For current behavior, use this precedence:

1. **Live on-chain contract/RPC facts** for on-chain SLH, BNB and TON.
2. **Production environment + canonical state** for gates, balances and settlement configuration.
3. **Runtime authority modules** for pricing, rewards and mutation semantics.
4. **Documentation** only when it matches the above.

A historical plan or stale UI copy must never override runtime evidence.

## 12. Corrections made on 2026-10-06

The previous tokenomics baseline contained these proven errors:

1. It described SLH as not on-chain, while the production system reads/transfers the BSC SLH token.
2. It described Credits as non-transferable, while the product supports internal Credit transfer.
3. It listed obsolete Stars packs (`450→500`, `800→1000`) instead of the canonical current packs (`500→550`, `1000→1200`).
4. It described the OS “no mint” policy too broadly; the correct claim is **no mint path in the SLH OS Alpha distribution authority**, not “the smart contract cannot mint.”
5. It implied that the internal SLH ledger and external on-chain SLH should be treated as one automatic balance; they are separate layers with explicit settlement paths.

This document is the canonical implementation baseline as of 2026-10-06.
