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
