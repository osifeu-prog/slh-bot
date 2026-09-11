# SLH Earn Center — Alpha UX Specification

## Goal

Make the user's first question easy to answer:

> How can I get SLH, what can I do with it, and what can I do next?

The Earn Center is a **read-first, evidence-driven UI**. It must not invent reward amounts, allocation promises, market prices, or returns.

## User-facing sections

1. **Available now** — actions that the current account and backend actually support.
2. **Complete to unlock** — Academy/tasks/onboarding steps that are verified requirements for an existing feature.
3. **Invite & community** — referral/community actions only when their current reward rule is authoritative.
4. **Use SLH** — verified utility such as supported wallet or product flows.
5. **Stake** — only the currently supported staking flow, with the asset and effect stated clearly.
6. **Alpha** — evidence/progress only; AIR allocation stays hidden until an authoritative allocation policy exists.
7. **Coming later** — capabilities that are not live, clearly marked as planned.

## Card contract

Every Earn card should answer four questions before the user taps:

- **What do I do?**
- **What do I receive?**
- **What are the conditions?**
- **When is it credited?**

If any of these are unknown, show `Policy not verified` instead of a guessed number.

## Current verified data sources

The Investor Read Model already exposes read-only wallet, personal task, reward-ledger, Academy, referral evidence, and Alpha-preview data. The Mini App should consume that existing snapshot rather than creating a second rewards system.

The current API also exposes authenticated task data. Task objects may contain a reward field, but the UI must not treat a raw legacy/test task reward as a universal SLH economic policy.

## Recommended home flow

```text
WELCOME
  ↓
YOUR WALLET
  ↓
YOUR NEXT BEST ACTION
  ↓
EARN / RECEIVE
  ↓
USE / STAKE / MARKET
  ↓
PROGRESS
```

## AI guidance

The AI entry point should provide contextual questions such as:

- "How can I get more SLH?"
- "What can I do with my SLH?"
- "Why can't I receive an Alpha allocation yet?"
- "What should I complete next?"
- "Explain Credits vs SLH."

The AI may explain verified state and guide navigation. It must not manufacture a reward amount, price, yield, allocation, eligibility decision, or transaction confirmation.

## Important market boundary

Historical project material contains claims about token price, liquidity, staking, airdrops, referrals, and purchase bonuses. Those historical values are not sufficient evidence for current economic policy. The public review also identified a mismatch between published supply and observed on-chain supply, enabled minting, a 1-of-1 treasury configuration, and negligible observed liquidity.

Therefore the UI must distinguish:

- **internal Credits**
- **SLH balance**
- **on-chain status**
- **AIR / Alpha allocation**
- **market price / liquidity**

No UI label may imply guaranteed profit or guaranteed liquidity.

## Release rule

The Earn Center can be implemented as navigation and read-only guidance now. Enabling a new financial mutation requires separate backend evidence, tests, policy, and explicit release approval.
