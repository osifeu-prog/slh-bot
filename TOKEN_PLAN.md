# SLH Token Plan — Product Vision vs Current Runtime

This file is a **product-vision document**, not a runtime source of truth.

## Vision

SLH is the ecosystem token intended to support:

- learning and contributor rewards;
- premium features;
- marketplace utilities;
- agent upgrades;
- governance/community features.

## Current runtime boundary

The current SLH OS implementation keeps **Credits and SLH separate**:

- Credits are the internal accounting unit for purchases, staking, rewards and the quote side of the SLH exchange.
- SLH is the BSC token plus an internal SLH ledger used by distribution and exchange authorities.
- The SLH OS Alpha distribution path does not mint SLH; it moves existing balances only.
- Verified on-chain SLH deposits can increase a user's internal SLH balance.
- A future decision to make “Credits = SLH” would require an explicit economic migration and reconciliation plan. This file does not authorize that migration.

## Non-authoritative historical language

Older versions of this plan said that users simply “earn SLH through activity.” That remains a product vision, not a sufficient description of the implemented Alpha accounting model.

Runtime code, production state and live on-chain evidence take precedence over this document.

## Operational SLH movement model

### SLH Move — internal ledger movement

“SLH Move” is the user-facing name for moving existing SLH between
canonical internal wallet ledgers.

- It transfers existing SLH only; it never mints supply.
- It is separate from an on-chain BSC transaction.
- It must use the canonical SLH ledger and atomic/idempotent transfer authority.
- A wallet security warning does not erase ownership history or block an
  unrelated internal SLH Move when the source is otherwise authorized.

### On-chain SLH movement

On-chain SLH transfers are a separate external-wallet operation:

- BSC Chain ID: 56.
- Token contract and decimals are canonical runtime metadata.
- The user's verified wallet signs/broadcasts the transaction.
- The server does not custody the private key or sign the transaction.

### Compromised-wallet boundary

A wallet marked `USER_REPORTED_COMPROMISED` is a security warning based on the
owner's report; it is not itself proof of compromise.

For such a wallet:

- do not use it as a source for real-money/on-chain outbound funding;
- do not send BNB there for gas;
- do not treat the warning as a transfer of ownership;
- do not block unrelated internal SLH Move or Treasury allocation from a
  separate verified source under the owner's control.

### Treasury allocation

Treasury allocation must reference a live, verified source balance. Treasury
amounts are runtime/on-chain facts and must not be hard-coded into this plan.
A reported Treasury quantity such as 26,332,942.28 SLH is therefore evidence
to reconcile against the live source before allocation, not a new supply event.
