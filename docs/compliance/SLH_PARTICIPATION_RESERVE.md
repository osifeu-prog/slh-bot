# SLH Participation / Reserve — Compliance Gate Specification

Status: DESIGN ONLY — NOT OPEN FOR PUBLIC FUNDING
Version: 1.0
Date: 2026-09-18

## Purpose
Define the architecture for a future SLH participation product in which users may place funds with the system for a defined term and receive a contractual economic return.
This document does not authorize solicitation, acceptance of funds, investment advice, marketing, or a guaranteed 65% return.

## Hard safety gates
Until written advice/approval from qualified Israeli counsel and any required regulator/licensed-provider review:
- Do not accept public investment deposits.
- Do not advertise or promise a 65% annual return.
- Do not describe internal staking as an investment product.
- Do not route investment funds into the existing internal state/db.json economy.
- Do not mix participant funds with ordinary operating revenue.
- Do not credit a participant merely because a payment was received.
- Do not enable an /invest or equivalent command.
- Do not activate an investment product in jurisdictions that have not been reviewed.

## Product separation
SLH must maintain separate domains:
1. SaaS / software revenue
2. Marketplace sales and services
3. Internal Credits and existing SLH staking
4. On-chain assets
5. Future regulated participation product

The future participation product must have its own participant ledger, treasury/reserve ledger, agreements, eligibility state, compliance audit trail, and reconciliation process.

## Proposed economic model
The business proposal currently under consideration is:
- 80% of defined distributable revenue allocated to reserves.
- A target economic return of up to 65% per annum for a one-year participation term.

These are business requirements, not legal or financial guarantees.
Before activation, counsel and financial/accounting review must define revenue vs gross revenue, permitted deductions, distributable revenue, reserve requirement, participant claim, return model, loss/default treatment, liquidity rules, tax treatment, accounting treatment, insolvency treatment, and marketing/disclosure language.
The system must reject the product configuration if required legal/accounting fields are missing.

## Eligibility state machine
UNREGISTERED -> KYC_REQUIRED -> KYC_PENDING -> KYC_APPROVED -> ELIGIBILITY_REVIEW -> ELIGIBLE -> AGREEMENT_REQUIRED -> AGREEMENT_ACCEPTED -> FUNDING_PENDING -> FUNDED -> ACTIVE -> MATURITY -> SETTLEMENT -> CLOSED

Failure states: KYC_REJECTED, ELIGIBILITY_REJECTED, JURISDICTION_BLOCKED, AGREEMENT_EXPIRED, COMPLIANCE_HOLD, SUSPENDED, DEFAULT_REVIEW.
No financial state transition may skip the required compliance state.

## Jurisdiction and eligibility
Before accepting funds, record customer jurisdiction/residency, citizenship where legally relevant, age, customer type, KYC status, sanctions/AML status, eligibility category, product version, and terms version.
Support jurisdiction-level ENABLED / REVIEW / BLOCKED configuration.

## KYC / AML
The implementation must support applicable identification, customer due diligence, record keeping, sanctions screening, suspicious-activity escalation, and retention requirements.
The exact obligations depend on the final legal classification and service providers used. They must not be guessed in application code.

## Money flow
Future architecture: User -> regulated/approved payment rail or segregated account -> compliance checks -> participant account -> approved treasury/reserve structure -> accounting/reconciliation -> settlement.
The existing internal SLH ledger remains separate.

## Reserve accounting
Minimum conceptual ledgers: operating_revenue, reserve, participant_principal, participant_return_accrual, participant_settlement, fees, tax_liability, exceptions.
Every movement requires immutable event ID, timestamp, source, destination, asset/currency, amount, legal/product version, participant ID where applicable, idempotency key, and reconciliation status.

## 65% return control
The number 65% must never be hard-coded as a guaranteed return in a public command or marketing response.
Configuration should contain a reviewed product parameter such as return_model, target_rate, rate_type, term_days, cap, minimum_reserve_ratio, legal_review_status, legal_review_reference, effective_from.
Activation requires legal_review_status=APPROVED plus all required operational controls.

## Reserve stress testing
Before activation, simulate 0% revenue; negative operating period; 25%, 50%, 75%, and 100% maturity concentration; revenue volatility; delayed receivables; reserve draw; default; payment-rail outage; fraud/chargeback; and FX/crypto volatility where applicable.
The system must show whether contractual obligations can be met under each approved scenario.

## Separation from existing staking
Existing SLH staking currently operates on internal Credits and creates stake_positions. It is not automatically a public investment product.
Any future participation product must use a separate product identifier and separate accounting boundary.
Do not repurpose staking_service.py or reward_engine.py into a public investment engine without a separate legal/product design.

## Marketing controls
Until approval: no promise of profit; no guaranteed 65% language; no safe-investment language; no implication that past performance guarantees future results; no public call to deposit funds; no referral commission tied to investment solicitation.
All public investment-related copy must be versioned and approval-gated.

## Audit and governance
Every approval-changing action must be auditable.
Required events include KYC decision, eligibility decision, jurisdiction decision, agreement acceptance, funding authorization, funding receipt, reserve allocation, accrual, settlement, refund, compliance hold, manual override, and legal-policy version change.
Owner/admin access must not permit silent deletion of financial audit records.

## Implementation order
1. Compliance/product specification.
2. Legal classification and counsel review.
3. KYC/AML provider and workflow selection.
4. Participant and compliance data model.
5. Segregated treasury/accounting model.
6. Eligibility engine.
7. Agreement/versioning.
8. Read-only reporting.
9. Sandbox funding tests.
10. External legal/compliance sign-off.
11. Controlled pilot if legally permitted.
12. Only then consider public activation.

## Current release decision
This feature is DESIGN_ONLY.
It must not be exposed as a funding product in Telegram, Mini App, website, or API until the activation gates above are satisfied.
