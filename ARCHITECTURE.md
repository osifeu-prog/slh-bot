# SLH OS Architecture

SLH OS is a Telegram-first application with a live Telegram Mini App for the user-facing experience. The system is organized around canonical state, controlled mutations, read-only evidence, and explicit settlement gates.

## Runtime layers

1. **Telegram Bot**
   - Primary command and interaction surface.
   - RBAC-aware handlers.
   - Developer Lab and owner-gated operational commands.

2. **Telegram Mini App**
   - User-facing UI for Wallet, Home, Move, Grow, Investor, Profile and related SLH views.
   - No separate end-user Dashboard is required.

3. **Flask / HTTP Control Plane**
   - Health, stats, logs, agents, tasks and Developer Lab API surfaces.
   - Operational/control endpoints are separated from user-facing Mini App flows.

4. **Core Services**
   - Economy and Credits
   - SLH token authority
   - Wallet binding and deposit verification
   - Exchange gate and matching
   - TON/BNB settlement gates
   - Academy, referrals, staking, governance and release readiness

5. **Canonical State**
   - `state/db.json` is the source of truth for runtime user/economy state.
   - `state/governance.json` stores governance-specific state.
   - Mutations should go through atomic service paths rather than manual file edits.

6. **RBAC and Authority**
   - Canonical roles include OWNER, ADMIN, DEVELOPER and USER.
   - Protected authorities remain outside ordinary Developer Lab write access.

7. **Governance**
   - Runtime commands include proposal, voting, tally, agent governance and sessions.
   - Votes flow through the governance store.
   - Approved proposals can bridge into developer missions.

8. **Developer Lab / CI/CD**
   - Developer proposal → OWNER approval → GitHub PR → CI → merge → Railway deployment.
   - Read-only checks provide production evidence without mutating state.

## Data flow

```
User
  │
  ├── Telegram Bot ────────┐
  │                        │
  └── Telegram Mini App ──┤
                           ↓
                    Core Services / RBAC
                           │
              ┌────────────┼────────────┐
              ↓            ↓            ↓
         Canonical DB   Governance   Settlement Gates
              │
              ↓
          Read-only Evidence
     /check /check_money /check_exchange
     /check_bnb /check_ton /alpha_status
```

## Exchange boundary

Internal Exchange is distinct from on-chain DEX execution.

- Internal Exchange uses verified SLH Live backing and internal Credits.
- Public order entry is fail-closed behind the exchange gate.
- `/check_exchange` is the canonical read-only exchange readiness surface.
- On-chain DEX execution is not implied by Internal Exchange being open.

## Settlement boundary

BNB and TON are separate external settlement systems.

- TON can be public-open only when its canonical readiness contract is valid.
- BNB remains closed until empirical deposit evidence is complete.
- A BNB gate state must never be inferred from Internal Exchange state.

## Production evidence

Current runtime health and release evidence should be obtained from the canonical read-only checks rather than stale documentation or manual DB inspection.
