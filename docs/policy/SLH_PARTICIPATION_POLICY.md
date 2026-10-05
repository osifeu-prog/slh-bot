# SLH Participation Policy v1.0

Status: DRAFT — pending legal/accounting review
Effective: TBD
Authority: docs/policy/SLH_PARTICIPATION_POLICY.md

## 1. Purpose

Define a future SLH Participation product separately from the existing Credits
staking prototype, the internal SLH economy, the P2P Marketplace, and external
assets such as BNB and TON.

This document defines product and accounting behavior. It does not authorize
public funding, solicitation, investment activity, or a guaranteed financial
return.

## 2. Participation Asset

Participation is denominated in the internal SLH asset defined by the approved
product policy.

It is not:
- Credits staking
- on-chain SLH
- BNB
- TON

No on-chain redemption is implied until an approved and operational settlement
path exists.

## 3. Term and Lock

Standard term: 365 days.

During the active term:
- early redemption is blocked;
- the participation position remains locked;
- secondary-market liquidity is not implied;
- external redemption is not promised.

At maturity, settlement is allowed only through an approved settlement policy
and an available operational path.

## 4. Revenue Sources

Participation rewards may be funded only from revenue sources explicitly
classified as eligible by the active policy.

Every eligible revenue event must have:
- source_revenue_id
- source type
- asset/currency
- amount
- timestamp
- verification state
- reconciliation state

Candidate source classes include verified external payments, approved service
revenue, and marketplace-derived revenue after its accounting treatment is
explicitly defined.

The following are not automatically eligible:
- internal Credit transfers;
- internal Credit marketplace settlement;
- referral Credits;
- test or boundary events;
- fake or unenforced payment records;
- historical/archived reward calculations;
- unreconciled treasury balances.

A P2P marketplace commission becomes Participation-eligible only after an
explicit accounting classification and reconciliation rule is implemented.

## 5. Distribution Basis

Distribution uses verified distributable revenue, not raw activity.

Conceptually:

  net_revenue = max(gross_revenue - approved_operating_costs, 0)

Where the approved policy specifies an 80% distributable share:

  distributable_pool = net_revenue * 0.80

The engine must never allocate more than the approved available pool.

## 6. Return / Cap Model

A mathematical annual cap may constrain the allocation of each participation
position.

The current design reference allows a parameter up to 65% per annum for a
one-year participation term, subject to approved product configuration,
reserve requirements, accounting treatment, and legal/compliance review.

The historical amount * 0.04 / 365 implementation in
archive/web3_disabled/staking_handler.py is historical evidence only. It is
not the canonical Participation authority and must not be reactivated as-is.

No fixed return is represented by this policy.

## 7. Eligibility

A participant position must satisfy all configured conditions before receiving
an allocation.

At minimum:
- valid participant identity;
- valid participation position;
- active term;
- eligible source revenue;
- valid policy version;
- successful calculation;
- required approval state.

Additional jurisdiction/compliance requirements may be added before activation.

## 8. Participation Position

Each position must contain at minimum:
- position_id
- participant_id
- asset
- principal
- created_at
- maturity_at
- status
- policy_version
- eligibility_state

Example lifecycle:

CREATED -> ACTIVE -> MATURED -> SETTLED

Possible hold/failure states:

COMPLIANCE_HOLD, SUSPENDED, DEFAULT_REVIEW, CANCELLED

## 9. Reward Event

Every allocation must be independently auditable.

Required fields:
- reward_id
- position_id
- source_revenue_id
- participant identity
- amount
- calculation timestamp
- calculation basis
- policy version
- approval actor/state
- idempotency key
- reconciliation state

A reward must never be created without a corresponding eligible source and
calculation record.

## 10. Ledger Separation

The system maintains separate accounting domains:

### Existing Credits / Economy
Existing wallet and Credits staking remain under their current authority.

### Existing Internal SLH
Existing SLH balances, transfers, and exchange reserves remain under the
current SLH authority.

### Participation
A new dedicated Participation ledger records positions, allocations,
accruals, maturity, settlement, and exceptions.

Ledgers are logically separate. A single business operation may link records
across domains only through an atomic transaction or an explicit
reconciliation protocol, with stable event identifiers.

## 11. Revenue-to-Participation Link

The canonical flow is:

Eligible Revenue Event
↓
Participation Pool
↓
Eligible Position Set
↓
Reward Calculation
↓
Reward Event
↓
Accrual / Settlement

The Participation engine must reference the original source_revenue_id. It
must never reconstruct revenue from wallet balances.

## 12. Redemption

Redemption during the initial 365-day term is blocked.

Post-maturity redemption requires a separate settlement policy defining:
- redemption asset;
- execution venue/path;
- pricing or exchange mechanism;
- liquidity source;
- fees;
- limits;
- failure handling;
- reconciliation.

No UI may imply guaranteed liquidity before that path is operational and
verified.

## 13. Safety and Integrity

The system must:
- reject duplicate reward events;
- reject invalid or unreconciled source revenue;
- reject double allocation against one revenue event;
- preserve immutable audit references;
- prevent negative balances;
- preserve source-to-reward traceability;
- prevent silent deletion of financial records;
- keep test records out of production reward calculations.

## 14. Current Status

Participation is DESIGN / POLICY DRAFT.

It is not active for public funding.

The existing Credits staking implementation must not be reclassified as
Participation by merely changing its lock period or reward formula.

## 15. Activation Gates

Activation requires, at minimum:
1. approved product policy;
2. accounting treatment;
3. legal/compliance review;
4. dedicated Participation ledger;
5. eligibility controls;
6. reward calculation engine;
7. audit events;
8. reserve/reconciliation controls;
9. sandbox/integration tests;
10. explicit release approval.

Until these gates are satisfied, the UI and bot must not present Participation
as an active return-bearing product.

## 16. Historical Implementations

archive/web3_disabled/staking_handler.py is historical evidence only.

Its amount * 0.04 / 365 calculation is not this policy's authority.

## 17. Authority Rule

When code, historical documentation, archived implementations, screenshots, or
AI responses conflict, the active approved Participation Policy and its
implementation authority take precedence.

Unverified values must be represented as Policy not verified.