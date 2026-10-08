# SLH OS Developer Onboarding

## Quick Start

SLH OS is a Telegram-first system with a live Mini App, Python handlers, canonical JSON state, RBAC, governance, exchange, staking, Academy, and payment/settlement boundaries.

### Source of truth

- Canonical state: `state/db.json`
- Governance state: `state/governance.json`
- Production: Railway
- Repository: `github.com/osifeu-prog/slh-bot`

## Developer access

1. Complete Bitcoin Mastery.
2. Send `/dev_request`.
3. OWNER reviews `/dev_requests`.
4. After approval, the account receives `role=DEVELOPER` and the Developer Lab permissions.

## Read-only audit surface

Use:

```
/dev_help
/dev_read <path>
/dev בדוק את Investor Overview שהגדרנו
/dev בדוק את הפקודות וה-collisions
/check
/check_ux
/check_money
/check_bnb
/check_ton
/check_exchange
```

These checks are read-only and do not change balances, wallets, settlement gates, or canonical state.

## Propose code changes

Use:

```
/dev_write <path> <summary>
```

Then provide the complete file content.

Flow:

```
Developer proposal
      ↓
OWNER approval
      ↓
GitHub branch + PR
      ↓
CI
      ↓
Merge to main
      ↓
Railway production deployment
```

Production is not edited directly by Developer Lab.

## Execution boundary

`/exec` is OWNER-only.

Developers use `/execr` for the bounded read-only audit path. The documented audit allowlist includes:

- cat
- grep
- find
- head
- tail
- sed -n
- awk

Protected production authorities and state paths remain outside Developer Lab write access.

## Governance

Governance is connected to the runtime.

Available commands include:

```
/gov_status
/propose <title> | <description>
/vote <proposal_id> <yes|no|abstain>
/tally <proposal_id>
/gov_agent_status
/agent_vote <agent_id> <approve|pause|revoke>
/session_new <agent_id> <summary>
/session_close <session_id> <outcome>
```

Votes are recorded through the canonical governance store. A proposal that reaches the configured approval threshold is marked approved and can automatically create a developer mission.

## Developer rules

1. Never edit `state/db.json` manually.
2. Do not bypass RBAC.
3. Use Developer Lab for code proposals.
4. Run the relevant CI and read-only checks before declaring a change production-ready.
5. Never expose bot tokens, API keys, wallet private keys, or other secrets.
6. New handlers must be registered through `handlers/loader.py`.

## Release evidence

The current production evidence surface is:

```
/check
/check_money
/check_exchange
/check_bnb
/check_ton
/alpha_status
/status
```

The Internal Exchange has a canonical read-only check with explicit public-gate and readiness status. BNB settlement remains independently gated and must not be inferred from Internal Exchange status.

## Wallet and settlement boundaries

- Internal Credits and staking are separate from on-chain assets.
- SLH Live balances are credited only from verified on-chain deposits.
- Internal Exchange transfers use existing verified SLH Live backing; the system does not mint SLH for exchange settlement.
- BNB public settlement remains closed until its required empirical evidence is complete.
