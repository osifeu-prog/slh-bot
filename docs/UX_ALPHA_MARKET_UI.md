# SLH Market UX — Alpha

## User principle
Users should complete common tasks through buttons, menus, contextual guidance, and the SLH AI assistant rather than memorizing commands.

## Navigation
- Home: portfolio snapshot and next recommended action.
- Wallet: balances, wallet binding/status, transaction history.
- Buy: Credits purchase flow.
- Stake: stake/unstake guidance and confirmation.
- Alpha: eligibility evidence and allocation status.
- Academy: learning progress and personal tasks.
- AI Help: contextual explanations and next-step guidance.

## UX rules
1. Every financial action has a clear confirmation step.
2. Show the asset and amount before confirmation.
3. Never show an allocation amount when policy is missing.
4. Explain unfamiliar terms inline.
5. Keep read-only on-chain information separate from internal balances.
6. Preserve Telegram Mini App authentication for protected API calls.
7. AI explains system state but does not bypass authority, permissions, or transaction controls.
8. Error states provide a human-readable reason and a next safe action.

## Alpha distribution UX
Eligibility → Policy check → Allocation approved → Distribution queued → On-chain confirmation.

Until an authoritative Alpha allocation policy exists, the Allocation state must remain `policy_missing` and amount must remain zero.
