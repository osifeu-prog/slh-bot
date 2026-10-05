# SLH Ecosystem Map — Participation Alignment

Status: WORKING MAP
Date: 2026-10-05

## 1. Current Production Boundaries

SLH OS
│
├── Internal Economy
│   ├── Credits
│   ├── internal SLH balances
│   └── existing Credits staking
│
├── P2P Marketplace
│   └── physical listings
│       └── buyer -> seller 90% -> treasury 10%
│
├── External Payment Revenue
│   └── verified Telegram Stars and other approved external sources
│
└── Future Participation
    ├── SLH internal participation position
    ├── 365-day term
    ├── revenue-source linkage
    ├── reward calculation
    ├── dedicated ledger
    ├── maturity
    └── approved settlement

## 2. Canonical Separation

Marketplace settlement is not automatically Revenue.

Revenue accounting is not automatically Participation allocation.

Participation allocation must reference a verified source_revenue_id.

Existing Credits staking is not Participation.

On-chain SLH, BNB, and TON are separate from the internal Participation asset.

## 3. Target Flow

Physical / approved ecosystem activity
        ↓
Verified revenue event
        ↓
Revenue eligibility
        ↓
Participation pool
        ↓
Eligible SLH participation positions
        ↓
Reward calculation
        ↓
Reward event + audit
        ↓
Accrual
        ↓
365-day maturity
        ↓
Approved settlement / redemption path

## 4. Existing Runtime Components

Credits staking authority:
core/staking_service.py

Current Revenue Share prototype:
core/staking_revenue_share.py

External revenue ledger:
core/revenue_ledger.py

P2P physical settlement:
store/purchase_service.py

Physical listing handler:
handlers/user_shop_handler.py

Internal SLH authority:
core/slh_distribution.py

## 5. Known Gaps

1. Participation policy is not yet an approved runtime authority.
2. Dedicated Participation ledger does not yet exist.
3. Revenue source classification for P2P commissions is undefined.
4. Existing staking uses Credits and defaults to a 30-day lock.
5. Redemption policy for a future Participation product is undefined.
6. Reward-engine approval/audit flow is not implemented as a dedicated layer.

## 6. Production Rule

No public Participation funding or return-bearing product activation until
the policy, accounting, compliance, ledger, tests, and release gates are all
approved.

Historical archive implementations are evidence only and are not runtime
authority.