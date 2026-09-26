# SLH Revenue & Rewards Hub

## Purpose

Connect the existing SLH monetization and reward rails into one authenticated
Mini App surface without creating a new monetary authority.

## Live composition

- Telegram Stars for digital goods and Credits.
- PayPlus card checkout for configured physical/hardware products.
- BNB and TON wallet binding and the currently configured deposit gates.
- WalletConnect for BSC wallet binding when its public Project ID is configured.
- Trade Scanner / Safe Mode / Trade Pro.
- Internal reward loops: Tasks, Academy, Referral, Staking and trusted Arcade events.

## Growth loop

Discover → Buy/Connect → Use → Earn → Upgrade → Return

The Hub is a read model and orchestration UI. It does not mint, settle, sign,
credit, or redistribute funds.

## Staged rails

USDT on TON is intentionally shown as staged until the legitimate Jetton master,
receiving-address policy and settlement verification are in place.

Live trade execution, bridge execution, copy-trade and sniper automation remain
behind the existing execution connector boundary.

## Owner observability

When the authenticated caller has exec.audit, the Hub may include confirmed
external revenue totals from the existing revenue ledger. This is observability,
not a new accounting authority.