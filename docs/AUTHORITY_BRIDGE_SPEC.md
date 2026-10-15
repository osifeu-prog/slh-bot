# AUTHORITY_BRIDGE_SPEC.md

**Status:** Documentation-only contract proposal. Not implemented, merged, or deployed.
**Date:** 2026-10-15
**Canonical identity/authority:** `osifeu-prog/slh-bot`
**WhatsApp/Twilio adapter:** `osifeu-prog/slh-api`
**Delivery order:** This is PR 1. Adapter code and any unrelated storage work must be separate later PRs.

## 1. Purpose

Define one narrow, authenticated bridge from the existing WhatsApp/Twilio adapter to SLH OS's canonical identity and authorization. Reuse existing services and identifiers; do not create a second bot, role table, ledger, exchange, referral program, or cross-repository Python import.

This document defines the contract for verified account linking, current permission checks, safe catalog and non-financial purchase inquiries, audit, idempotency, revocation, and fail-closed behavior. It does not authorize checkout or WhatsApp trading.

## 2. Evidence from the operator-provided production outputs

These facts come from the supplied read-only outputs dated 2026-10-15, not from a new live production query.

### Referral path and storage
- `handlers/share_handler.py` builds links in the form `?start=ref_<telegram_id>`.
- `handlers/onboarding_v2.py` parses `/start ref_<telegram_id>`, checks that the referrer exists, sets pending attribution for a new user, and calls `core.referral_attribution.record_referral_start`.
- `core/referral_attribution.py` uses `state_manager.atomic_update` for `referral_start_events` and `pending_referrals`; referral rewards remain in the existing successful-join path.
- The supplied active DB check reported `DB_FILE=state/db.json`, 33 users, `pending_referrals=<MISSING>`, `referral_start_events=<MISSING>`, and zero users with `referral.referred_by`.
- The supplied scan found 385 `growth_events`, zero referral/share matches, and no matching referral-attribution error lines in the scanned log files.
- The 11:47 source grep found `handlers/share_handler.py` building `ref_<uid>` links, `handlers/onboarding_v2.py` parsing `ref_` and calling `record_referral_start`, and `handlers/join_handler.py` persisting `referred_by` and settling rewards only in the successful-join path.
- The 11:49–11:50 excerpts show `handlers/loader.py` includes `("onboarding", "handlers.onboarding_v2")` and invokes a supported registration function, while `handlers/onboarding_v2.py` has `@bot.message_handler(commands=["start"])` and the referral-payload branch that calls `record_referral_start`.
- These last results establish a **static source/loader path**. They are not a captured runtime snapshot of the production TeleBot registry and do not prove that a specific inbound referral update reached the handler. `core/runtime_command_evidence.snapshot_runtime("Me_ad_main")` can expose live registered command handlers when invoked in the running process; no resulting `/start` handler entry was included in the supplied output.

**Interpretation:** The supplied DB snapshot contains no recorded referral attribution. It does not prove that nobody ever opened or clicked a Telegram link; it means no qualifying referral start is evidenced in that snapshot. The code/loader path is present, so do not patch referral code, backfill users, rewrite `code`, or fabricate referral records without new failing runtime evidence.

### Exchange and external settlement
- The operator's 11:30 narrative reported trades `T24` and `T26`, four trades total, zero open orders, order-book/money invariants passing, and a public gate open.
- The supplied 11:10 `/check_exchange` output reported `open_orders=1`, `public readiness=FAIL`, and `BLOCKED`.
- The supplied BNB result reported public BNB gate CLOSED and evidence BLOCKED by `HISTORICAL_BNB_DEPOSIT_LEDGER_REVALIDATION_FAILED`, despite empirical smoke and live RPC showing PASS.
- Owner `/start` at 11:42 displayed Credits `30.072775`, Staked `794`, Internal SLH `9`.

These are time-separated/conflicting exchange snapshots. Require fresh canonical evidence before any future integration that depends on a currently healthy exchange. Do not treat an earlier PASS as current proof. BNB and TON remain CLOSED until their independent canonical evidence gates pass.

## 3. Repository and identity boundaries

### Canonical authority
`osifeu-prog/slh-bot` owns canonical Telegram identity and authorization through `core.authority.get_role` / `has_permission`, canonical user profiles and referral attribution.

### WhatsApp adapter
The existing `slh-api` adapter owns Twilio/provider interaction, including signature validation, contacts and provider message IDs. The supplied audit identifies `whatsapp_contacts.user_id` as an existing BIGINT field. That field is a legacy link/projection, not proof of account ownership by itself.

The adapter's `ADMIN_USER_ID` and the canonical SLH `OWNER_ID` are distinct authority concepts. Do not substitute one for the other. The WhatsApp service must never impersonate either.

### Prohibited shortcuts
- No cross-repository Python imports and no direct read/write of the bot's `state/db.json` from `slh-api`.
- No local copy of canonical roles/permissions in `slh-api`.
- No trust based only on an imported contact, phone number, display name, self-declared UID, or legacy `whatsapp_contacts.user_id`.
- Do not reuse `/internal/telegram/mcp-proof` for identity linking or commerce; it is read-only connectivity proof.
- Do not use broad MCP, OWNER, ADMIN, or other wildcard credentials as the WhatsApp service credential.
- Do not create a second referral implementation or a new ad-hoc identity-mapping module.

## 4. Verified pairing protocol

The flow must prove both that the Telegram account requested the link and that the inbound WhatsApp message came from the provider-verified phone.

1. An authenticated Telegram user starts the linking flow in the canonical bot. The Control Plane generates a cryptographically random, single-use code (at least 128 bits of entropy), stores only its hash, binds it to the canonical Telegram UID and gives it a short expiry (recommended: 10 minutes).
2. Deliver the code only to the same authenticated Telegram user. Rate-limit issuance and failed attempts. Never log the raw code.
3. The customer sends the code on WhatsApp. Before parsing or handling, `slh-api` validates the provider signature against the raw request and canonical external callback URL. The sender phone and provider message SID must come only from the verified provider payload.
4. The adapter submits provider, sender, message SID, and code to the dedicated internal pairing contract. It must not submit a caller-selected Telegram UID.
5. The Control Plane verifies expiry, unused status, attempt limits, provider-message idempotency and normalized sender; atomically consumes the code and records the canonical link reference. Conflicting links fail closed.
6. Only after successful Control Plane response may the adapter set `whatsapp_contacts.user_id` to the returned canonical UID. This remains a projection/cache for existing SQL workflows, not the source of authorization.
7. Every subsequent account-specific action revalidates the active link and current canonical role/permissions. A mismatch between the contact row and the canonical link is denied and sent to reconciliation; it is not silently overwritten.
8. Support canonical link revocation. Unlinked, expired, revoked, conflicting or ambiguous identities cannot access private data or create account-specific inquiries.

Choose one consistent protected canonical storage mechanism for challenge/link/revocation state. Do not store raw pairing codes, and do not introduce unnecessary copies of full phone numbers in the canonical JSON DB; use a documented keyed digest or equivalent protected reference where lookup requires it.

## 5. Proposed internal contract (not yet deployed)

These route names are proposals for review, not assertions that live endpoints already exist. If implementation finds an equivalent canonical endpoint, document and reuse it instead of creating a parallel API.

All internal routes require HTTPS, a dedicated least-privilege service identity and credential, size/rate limits, audit, no-store responses and idempotency. Never pass internal responses directly to customers.

### A. Start pairing — canonical Telegram side
Logical operation: `create_whatsapp_pairing_challenge(telegram_uid)`.
- UID comes only from validated Telegram update / authenticated Mini App session.
- Check the canonical user and policy; create a hashed, expiring, one-use challenge.
- Return the code only to that authenticated user.
- No referral, balance or reward mutation.

### B. Complete pairing
**Proposed:** `POST /internal/authority/v1/whatsapp/links/complete`

Request: `provider` (initially `twilio`), verified `provider_message_id`, `verified_phone_e164`, `pairing_code`.

Never accept caller-authoritative `telegram_uid`, `role`, `permissions`, or a user mapping as input. Derive service identity from credential, not request JSON.

Minimum successful internal response: `status="LINKED"`, opaque `link_id`, `telegram_user_id` for the authenticated adapter to update its existing `whatsapp_contacts.user_id` projection, and `duplicate`. Same message replay returns the original result; altered replay (different phone/code) is a conflict. Do not return this response directly to a customer.

### C. Resolve and authorize each action
**Proposed:** `POST /internal/authority/v1/whatsapp/authorize`

Request: provider, provider message SID, provider-verified sender phone, opaque `link_id`, and allowlisted action (`catalog.read`, `purchase_inquiry.create`, optional `referral_link.read`).

The Control Plane verifies the canonical link matches the verified sender, checks status/revocation, resolves current canonical user identity, calls `get_role` / `has_permission`, and makes the decision. A UID, role, permission or eligibility supplied by the caller is never authoritative. Return only allow/deny, a safe reason code, and the minimum customer-facing capability needed.

Do not expose personal balance, private profile, internal exchange controls, admin/system checks, arbitrary command execution or general MCP tools through this bridge.

### D. Canonical catalog
**Proposed:** `GET /internal/commerce/v1/whatsapp/catalog`

Return only currently published, owner-approved products with canonical name/description, exact price/currency and supported next step. Do not invent prices, availability, terms, returns or ROI. If a product is only purchasable using Telegram Stars, explicitly say payment takes place through Telegram and not inside WhatsApp.

### E. Non-financial purchase inquiry
**Proposed:** `POST /internal/commerce/v1/whatsapp/intents`

Request: verified provider/message SID, active canonical link for account-specific requests, approved SKU, `intent="purchase_inquiry"`, explicit customer confirmation, and idempotency/correlation key.

The Control Plane validates product, identity and policy; returns opaque `intent_id` and `status="inquiry_pending"`. Identical replay returns the original record. Reusing the key with a different SKU, identity or intent returns conflict.

An inquiry must not debit/credit Credits, write revenue, reserve exchange funds, place/cancel an order, mint/transfer SLH, create a payment claim, pay out, or fulfil an item. It never returns a paid or fulfilled receipt.

### F. Dedicated service identity and scope
Use a separate service credential/principal, distinct from OWNER UID and `ADMIN_USER_ID`. The canonical Control Plane should grant only explicit scopes (proposed):
- `whatsapp.identity.pair` — complete an already initiated pairing challenge;
- `whatsapp.catalog.read` — read the customer-safe published catalog;
- `whatsapp.intent.create` — create idempotent non-financial inquiries;
- `whatsapp.referral_link.read` — optionally return a canonical referral link if approved.

Default-deny all other permissions. Explicitly deny `exec.audit`, `agents.manage`, `agents.modify_self`, `economy.mutate_self`, admin APIs, order execution and settlement. An OWNER/ADMIN/DEVELOPER wildcard role is never acceptable for the WhatsApp service identity. Missing/invalid service configuration fails closed.

## 6. Allowlisted WhatsApp actions

Phase A may support `help`, `catalog`, `price <sku>`, `link`, and `buy <sku>` only as an account-eligible non-financial inquiry after verified pairing and canonical authorization. Unlinked senders may receive help and a public catalog only. They cannot retrieve personal details or submit an account-specific inquiry.

Treat all message text as untrusted input. Never interpret it as shell, SQL, arbitrary commands, URLs to fetch, or an instruction to grant admin rights. Clearly state that a `buy` response is an inquiry for follow-up, not a payment or completed order.

## 7. Referral behavior: reuse the existing path

- Keep the existing Telegram `/start ref_<telegram_id>` path and first-touch attribution.
- The WhatsApp adapter never writes `pending_referrals`, `referral_start_events`, `users.referral`, referral counts, Credits or Points directly.
- Customers who want to invite someone are redirected to the canonical Telegram referral link/bot; existing Telegram `/start` processing handles attribution.
- A WhatsApp message, catalog visit, click, contact import or pairing is not a successful referral and grants no reward by itself.
- Referral rewards remain exclusively in the current successful-join path. Do not backfill `code`, fabricate historical events, or create another referral source.

## 8. Default-off and financial boundary

Required defaults:
- `WHATSAPP_STORE_ENABLED=0`;
- `WHATSAPP_STORE_CHECKOUT_ENABLED=0`.

This documentation PR must not add production secrets/variables or change deployment, DB, wallets, balances, referral state, orders, revenue, token or settlement gates. First implementation is limited to provider verification, verified pairing, safe catalog reads and non-financial inquiry. WhatsApp must not initiate trades or payments. Any future exchange integration needs a fresh canonical exchange check because the supplied snapshots conflict. BNB and TON remain CLOSED until independent settlement evidence and gates are green and explicitly reviewed. A WhatsApp flag never overrides a canonical gate.

## 9. Requirements for the later `slh-api` adapter PR

1. Verify provider signature against raw request and canonical external URL before any side effect.
2. Derive sender and message SID only from verified provider payload.
3. Enforce strict intents, request-size limits, per-sender rate limits, replay/idempotency controls and bounded retries.
4. Call only the internal contracts using a dedicated credential.
5. Update `whatsapp_contacts.user_id` only after canonical pairing succeeds; imported contacts are not verified identities.
6. Revalidate authorization for every private/account-level action; fail closed on timeout, invalid response, revoked link or mapping mismatch.
7. Do not log tokens, raw codes, complete phone numbers, message bodies or provider secrets; retain only necessary metadata under a documented retention policy.
8. Leave current invite/fraud/broadcast behavior unchanged. Any later marketing requires recorded opt-in and opt-out.
9. Never access the bot DB directly or import bot modules across repositories.

## 10. Acceptance tests before implementation approval

- Invalid/missing provider signature is rejected before state mutation.
- Missing/wrong/expired/reused pairing code cannot create/change a link.
- The adapter cannot supply/override a Telegram UID or role.
- An imported contact or legacy `user_id` without an active canonical link is denied.
- Current canonical roles/permissions are checked; revoked identities fail.
- Service identity cannot use OWNER/ADMIN/DEVELOPER wildcard or unrelated permissions.
- Catalog includes only canonical published products/prices; no fallback data.
- Unknown SKU, duplicate SID, modified replay, Control Plane outage, malformed response or missing permission fails closed.
- Identical inquiries create one record; altered replay conflicts.
- Inquiry creates no balance, Credits, revenue, reserve, order, token, settlement or fulfilment mutation.
- Closed BNB/TON rails cannot be displayed as available or initiated.
- WhatsApp does not mutate referral storage/rewards; existing Telegram referral tests stay green.
- Secrets/full phone/message contents never appear in logs or public errors.
- Existing contact/invite/fraud/broadcast tests remain green.
- Store and checkout flags default off; tests do not mutate production state/configuration.

## 11. Delivery order

1. **PR 1 — this file only:** review/approve `AUTHORITY_BRIDGE_SPEC.md`; no code or production changes.
2. **PR 2 — `slh-api` adapter:** only after PR 1 approval and confirmation of the canonical contracts. Implement provider verification, pairing interaction, safe catalog and inquiry. Keep it disabled by default.
3. **PR 3 — `Tax_Free_world_bot` / `aiosqlite`:** separate task and review; not a dependency of this bridge unless scope is explicitly changed.
4. **Rollout:** no deployment/flag change until code review, CI/security and signed-webhook end-to-end tests pass and deployment is explicitly approved.

An earlier exploratory code branch is not approval to skip the documented order. This spec is the contract baseline.
