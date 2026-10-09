# ZUZ — BSC compromised-address quarantine and forensic tracking

**Status:** QUARANTINED / READ-ONLY FORENSICS  
**Record date:** 2026-10-09  
**Classification source:** owner-reported compromise; this document does not independently prove who controlled the address or who initiated any transaction.

## Address identities

| Role | Value | Rules |
|---|---|---|
| Owner's Trezor wallet (owner-provided) | `0x468328B2a7C9b5629e87844Bb4531e7409400b34` | May be used only after existing wallet-ownership verification. This classification does not automatically make it a Treasury. |
| Compromised address / forensic label ZUZ | `0x693db6c817083818696a7228aebfbd0cd3371f02` | Must not be used as BNB/SLH Treasury, deposit target, verified operational wallet, or BNB/SLH transfer recipient. |

## Operational controls

- BNB readiness must fail closed if either the configured Treasury or `SLH_BSC_CANONICAL_TREASURY` is the quarantined address.
- BNB and SLH deposit verifiers must reject the quarantined Treasury before contacting the RPC.
- Wallet-binding challenge/verification, native BNB transfer preparation, ERC-20 transfer preparation, secondary SLH distribution, owner SLH browser handoff, and direct Mini App SLH transfer must reject it.
- The public BNB wallet status must not render it as an actionable deposit target.
- Existing state and transaction history must be preserved. Quarantine is not a reason to delete ledger entries, revoke unrelated users, or change balances manually.
- BNB settlement remains closed until its separate empirical evidence and gate pass. This quarantine work does not open BNB, on-chain swap, Participation, Investment, or IDO.

## Meaning of ZUZ

In this change, **ZUZ is a forensic classification/identifier for tracking evidence related to this address**. It is not a new on-chain contract, does not claim the address holds ZUZ, and does not create or credit any internal balance. The current source files inspected for tokenomics, economy, asset registry, market and financial truth did not expose a canonical ZUZ ledger authority. A true ZUZ-denominated internal ledger must be implemented as a separate canonical, audited service rather than inferred from this address label.

## Forensic workflow

1. Preserve the address and all relevant historical transaction hashes; do not send funds to it.
2. Collect chain-56 transaction hashes, blocks, receipts, input data, token Transfer logs, approvals/allowances, and timestamps from a trusted explorer/RPC.
3. Trace outgoing transfers to subsequent addresses and contracts; distinguish confirmed on-chain facts from hypotheses.
4. Identify a real-world actor only if separate attributable evidence supports it. A blockchain address alone does not establish the identity of a person.
5. Keep findings and source links in a dated incident record. Do not expose secrets, recovery phrases, private keys, or signed payloads.

## Fail-closed error

Operational attempts targeting this address return `BSC_ADDRESS_QUARANTINED_ZUZ`. The user-facing error intentionally does not repeat the full address.
