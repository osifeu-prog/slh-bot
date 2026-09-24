# Secure Wallet Binding & Deposit UX — Design Specification

## Goal

Enable verified user binding for BNB and TON wallets and expose the existing, authenticated deposit paths through the SLH OS Mini App and website integration without creating duplicate wallet authorities, duplicate deposit handlers, or mixing internal SLH balances with on-chain assets.

## Current System Evidence

The current `main` branch already contains:
- BNB ownership binding in `core/wallet_binding.py` using a challenge/signature flow.
- BNB settlement in `core/bnb_deposit_service.py`, which requires an existing verified binding and credits Credits only.
- BNB claim routing in `handlers/claim_handler.py`.
- TON information/legacy claim handlers in `ton_handler.py` and `handlers/ton_claim_handler.py`, both intentionally paused.
- TON read helpers in `core/ton_lab.py`.
- A Mini App served by `webapp.py` and implemented in `mini_app.html`.
- Canonical internal economy state in `state/db.json`.
- Separate on-chain/read-only data surfaced from `slh-api`.
- Internal SLH is explicitly modeled as `on_chain=False`; BNB and TON are external on-chain assets.

The live state currently has no verified BNB bindings, no per-user TON wallet binding, and `ton_address`/legacy TON claim paths are paused. BSC RPC connectivity is live and reports a treasury balance for the configured SLH contract.

## Non-Negotiable Boundaries

1. Do not create a second BNB binding authority. Reuse `core.wallet_binding`.
2. Do not create a second BNB deposit authority. Reuse `core.bnb_deposit_service`.
3. Do not trust a submitted wallet address or TX hash by itself.
4. Do not credit a user merely because a TX exists on-chain; the sender must match a previously verified user binding and the receiver must be the configured treasury.
5. TON must use a cryptographic ownership proof (TON Proof / ton_proof through TON Connect or an equivalent supported proof flow) verified server-side.
6. Deposit idempotency is keyed by transaction hash and must not double-credit.
7. Internal SLH (`state/db.json`) and on-chain BSC SLH (`slh-api` / BSC contract) remain separate sources of truth.
8. No mint, burn, redistribution, supply migration, or provenance compensation is part of this feature.
9. Existing Exchange, P2P, Credits, Academy, staking, and rewards paths must not be duplicated or reimplemented.
10. Existing Mini App Telegram authentication remains the identity boundary for private APIs.
11. Website public AI intake remains public; wallet binding endpoints require authenticated Telegram identity where the user account is involved.
12. Existing paused TON and BNB user-deposit behavior must not be silently advertised as active until the verified binding flow is deployed and live-tested.

## Architecture

### BNB

Reuse:
- `core.wallet_binding.py` for normalize/challenge/verify/get_binding.
- `webapp.py` endpoints `/api/wallet/bnb/challenge`, `/api/wallet/bnb/verify`, and `/api/wallet/bnb`.
- `core.bnb_deposit_service.settle_bnb_deposit`.
- `handlers/claim_handler.py` for Telegram /claim.

The Mini App gains a clear connection/status surface and invokes the already-existing endpoints. No second BNB wallet table or handler is introduced.

### TON

Add one canonical TON binding authority under `core/`, parallel in responsibility to `core/wallet_binding.py`, for example `core/ton_wallet_binding.py`.

It owns:
- challenge generation with TTL and one-time nonce,
- normalized TON account/address representation,
- verification of server-issued TON Proof,
- one binding per Telegram account,
- one Telegram account cannot own multiple active TON bindings unless a future explicit replacement workflow is introduced.

The Mini App uses TON Connect for wallet connection and obtains a server-verifiable TON Proof. The backend verifies the proof against the challenge/domain/address/account payload before storing the binding.

The existing `core/ton_lab.py` remains a read/experiment utility and is not upgraded into the ownership authority. The existing `ton_handler.py` remains the user-facing Telegram information/command surface. The existing `handlers/ton_claim_handler.py` remains disabled until the new authority is wired to a verified claim flow; it is not replaced by a duplicate handler.

### Deposit settlement

BNB:
Telegram/WebApp authenticated UID -> verified BNB binding -> verified BNB transaction -> `core.bnb_deposit_service` -> Credits.

TON:
Telegram/WebApp authenticated UID -> verified TON binding -> verified TON transaction to the configured TON treasury -> canonical economy mutation through an idempotent settlement service -> Credits.

For TON, the new settlement service must separate:
- ownership verification,
- on-chain TX verification,
- economic mutation.

A TON deposit must satisfy both layers:
- the sender must equal the previously verified TON wallet binding;
- the inbound transaction must carry the requesting user's personal memo `SLH<uid>`.
The memo is an additional transaction identifier and is never treated as proof of wallet ownership.

No TON private keys are stored or used.

## UI and Integration

### Mini App

Extend the existing wallet section in `mini_app.html` rather than adding a second wallet page.

Display:
- Internal Credits.
- Internal SLH.
- Staked.
- Existing on-chain `slh-api` balances.
- BNB binding state: Not connected / Verified address.
- TON binding state: Not connected / Verified address.
- Clear deposit action only when the corresponding verified binding and settlement route are available.

The Mini App remains private/account-scoped under Telegram initData. Direct browser access keeps the existing auth gate.

### Website

The website should consume the same backend binding endpoints and display the same account state rather than implementing separate signing, binding, or deposit logic. Where the site is public, it may explain the process and link the user into Telegram/Mini App for account-bound verification. No second website-specific wallet database is introduced.

Because the currently connected GitHub repository exposes `slh-bot` but not the website repository, website code changes require access to the actual site repository/service source before implementation; the contract is nevertheless fixed here so the website can integrate without changing backend authority.

## Data Model

BNB existing storage is preserved:
- `wallet_bindings`
- `wallet_challenges`

TON adds:
- `ton_wallet_bindings`
- `ton_wallet_challenges`
- optional verified-binding metadata required for proof-domain/chain/account normalization.

Settlement records remain in the existing economy ledger with:
- explicit asset/source metadata,
- transaction hash,
- binding address,
- idempotency key.

No balance is copied from on-chain assets into internal SLH.

## Security and Failure Behavior

- Missing Telegram initData: reject account-bound API calls.
- Invalid/expired/consumed challenge: reject.
- Invalid signature/proof: reject without state mutation.
- Address does not match proof: reject.
- Wallet already bound to another UID: reject.
- User already has a different verified wallet on the same chain: reject until a dedicated replacement workflow exists.
- TX sender does not equal bound wallet: reject.
- TX recipient does not equal treasury: reject.
- Failed/unconfirmed TX: reject.
- Already-recorded TX hash: return idempotent/no-second-credit result.
- Any partial settlement failure must leave the economic mutation atomic.

## Deposit Economics Safety Gate

TON user deposits remain closed by default. Opening requires:
- runtime kill switch `TON_DEPOSITS_OPEN=1`;
- one configured canonical TON treasury address;
- a Credits/TON rate inside the approved 100–110 safety band.

A configured rate outside the band must fail closed rather than crediting at the unsafe rate.

## Testing

Before implementation is considered complete:
- BNB existing tests must continue to pass.
- Add BNB live-compatible route tests covering verified binding, mismatched sender, unbound wallet, and duplicate TX.
- Add TON proof-verification unit tests covering valid proof, invalid signature, wrong address, expired nonce, reused nonce, and wallet already bound.
- Add TON settlement tests covering wrong sender, wrong treasury, failed/unconfirmed TX, duplicate TX, and successful atomic Credits credit.
- Add Mini App tests proving it renders binding state and never exposes account-bound controls outside Telegram authentication.
- Add regression checks ensuring Exchange, P2P, Gifts, Academy, and staking are not registered twice and their existing authority modules remain the only mutators.
- Run the full project test suite before deployment.

## Release Gates

1. Tests green.
2. No duplicate handler/authority registration.
3. Mini App updated against the existing endpoints.
4. Backend deployed successfully.
5. Live BNB binding E2E verified.
6. Live TON binding E2E verified.
7. Live deposit settlement E2E verified at least once per chain with idempotency replay.
8. Website integration verified when the actual site source is available.
9. Only after all gates pass are BNB/TON user deposit surfaces considered opened.

## Explicitly Out of Scope

- Recovering or redistributing historical internal SLH balances.
- Changing the internal SLH supply.
- Connecting external BSC SLH directly to internal `wallet.token_balance`.
- Creating a new Exchange implementation.
- Creating a new P2P implementation.
- PC/ESP wallet control as a financial authority.
