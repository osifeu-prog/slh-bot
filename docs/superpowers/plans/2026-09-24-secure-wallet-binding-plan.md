# Secure Wallet Binding & Deposit UX — Implementation Plan

## Scope
Implement the approved secure BNB/TON binding and deposit flow, align the existing Mini App and wallet UX, and keep internal SLH/on-chain assets separate.

## Non-negotiables
- BNB reuses core.wallet_binding and core.bnb_deposit_service.
- TON uses one canonical proof-binding authority and one settlement authority.
- Telegram initData remains the account identity boundary for private APIs.
- TON requires TON Proof plus a one-time server challenge.
- TON settlement requires bound sender, treasury recipient, positive value, and the personal SLH<uid> memo.
- Credits mutations use the existing atomic economy authority and TX-hash idempotency.
- TON deposits stay closed unless TON_DEPOSITS_OPEN=1 and the configured rate is within the approved 100–110 Credits/TON safety band.
- No internal SLH mint/burn/redistribution/provenance reconciliation.
- No new Exchange/P2P/Academy financial authority.
- Site wallet connection may display provider state, but verified ownership must come from the canonical backend.

## Tasks
- [ ] Freeze authority boundaries with regression tests and duplicate-handler checks.
- [ ] Keep BNB binding as the sole BNB ownership authority and expose it in the existing Mini App Wallet section.
- [ ] Add TON Proof binding with challenge TTL, nonce consumption, address/network/domain checks, StateInit-derived address/public key validation, and one-wallet-per-user/one-user-per-wallet constraints.
- [ ] Add canonical TON settlement using the existing atomic record_ton_deposit authority, TX idempotency, bound sender, treasury recipient, memo, and rate guard.
- [ ] Make handlers/ton_address_handler.py the sole owner of /ton_check and /ton_paid; leave legacy /claim_ton disabled.
- [ ] Add authenticated Mini App BNB/TON status and verification UI; distinguish connected from verified.
- [ ] Fix stale Academy→Staking copy; Academy remains independent from Staking.
- [ ] Align Telegram /wallet with actual binding/open status.
- [ ] Enrich Bitcoin Mastery lessons 1–12 to the approved seven-part learning standard; do not publish the separate SLH self-test module yet.
- [ ] Keep course monetization decision unresolved until owner chooses free vs paid split; do not silently remove or gate the course.
- [ ] Website integration remains pending writable site-repo access; existing site components and payment endpoints were audited for later hardening.
- [ ] Run project tests and live BNB/TON E2E before enabling deposits.
- [ ] Verify production Railway deploy and document exact evidence in docs/INCIDENTS.md.

## Verification
1. Python compile/static validation.
2. Targeted wallet/TON tests.
3. Full pytest suite.
4. Handler uniqueness.
5. No new internal SLH supply mutations.
6. BNB live bind + deposit + replay + wrong-sender test.
7. TON live bind + deposit + replay + wrong-sender test.
8. Mini App Telegram auth and wallet regression.
9. Site regression after writable source access.
10. Only after all gates: enable TON_DEPOSITS_OPEN and public deposit copy.

## Explicitly deferred
- Historical 44M internal-SLH provenance incident.
- Four 40K unbacked test-residue balances.
- PC/ESP financial authority.
- Any direct linkage of external BSC SLH to internal SLH.
