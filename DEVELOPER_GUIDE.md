# SLH OS Developer Guide

## Getting Access

1. Complete Bitcoin Mastery:
   - /course_bitcoin_mastery
   - /lesson bitcoin_mastery 1
   - /finish bitcoin_mastery 1
   - repeat for lessons 2 and 3
2. Send /dev_request.
3. OWNER reviews /dev_requests.
4. After approval you receive `role=DEVELOPER` and the Developer permissions.

## After Approval

### Read-only audit

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
```

These read-only checks do not mutate wallets, settlement, or production state.

### Propose a code change

```
/dev_write <path> <summary>
<complete file content>
```

A proposal is stored first. OWNER approval creates a GitHub branch and pull request.
CI runs on the PR. Merge and production deploy remain controlled separately.

### Request an approved audit command

```
/execr <command>
```

Developers are limited to the read-only audit allowlist such as:

- cat
- grep
- find
- head
- tail
- sed -n
- awk

Commands outside the audit allowlist require explicit OWNER approval through the execution policy.

### Important: /exec vs /execr

`/exec` is OWNER-only.

Developers use `/execr` for the read-only audit path.

## Developer Rewards

Verified Developer Lab pull requests that are merged to `main` are eligible for:

- First merged PR: **5,000 Credits**
- Each additional merged PR: **2,500 Credits**
- After 3 merged PRs: OWNER may discuss an optional SLH bonus from existing supply. This is not a mint, guarantee, or contractual reward.

OWNER verifies a merged PR with:

```
/dev_reward_pr <user_id> <merged_pr_number>
```

The reward authority verifies that the PR is merged into `main`, came from the Developer Lab flow, and has not already been rewarded.

## Project

- Repository: github.com/osifeu-prog/slh-bot
- Production: Railway
- Main entrypoint: `bot_gateway.py`
- Handler loader: `handlers/loader.py`
- Canonical state: `state/db.json`

## Protected Areas

Never edit production state manually.

Developer Lab does not permit proposals to protected authorities such as:

```
.env
Dockerfile
railway.json
core/authority.py
core/exec_policy.py
core/telegram_webapp_auth.py
core/wallet_binding.py
core/ton_wallet_binding.py
core/ton_deposit_service.py
core/bnb_gate.py
core/bnb_deposit_service.py
core/deposit_monitor.py
core/economy_service.py
core/railway_control.py
handlers/exec_handler.py
handlers/exec_request_handler.py
handlers/e_handler.py
state/
.github/
```

## Contribution Rules

1. Do not edit `state/db.json` manually.
2. Use Developer Lab for code proposals.
3. Do not bypass RBAC or wallet signing controls.
4. New handlers must be registered through `handlers/loader.py`.
5. Never expose bot tokens, API keys, wallet private keys, or other secrets.
