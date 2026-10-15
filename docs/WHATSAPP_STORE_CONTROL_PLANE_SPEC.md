# SLH WhatsApp Store via the Existing Control Plane

**Status:** Draft architecture specification only — not implemented or deployed.
**Coordination repositories:** `osifeu-prog/slh-bot` (canonical Control Plane) and `osifeu-prog/slh-api` (WhatsApp/Twilio adapter).
**Feature flags (proposed, default off):** `WHATSAPP_STORE_ENABLED=0`, `WHATSAPP_STORE_CHECKOUT_ENABLED=0`.

## 1. Evidence and current boundary

Inspection of `slh-api/routes/whatsapp.py` shows existing `whatsapp_contacts`, `whatsapp_invites`, admin-protected contact management, outbound Twilio invites/broadcasts, fraud flags and audit records. The inspected module does not expose an inbound customer-message webhook, a catalog endpoint, a purchase-inquiry flow, or a verified WhatsApp-to-SLH account pairing flow.

The canonical Control Plane is deployed from `osifeu-prog/slh-bot` in Railway project `slh-os-control-plane`, with `web` and `slh-mcp` services. `slh_mcp/control_plane_client.py` wraps agent/mission routes; the MCP capability catalog does not define WhatsApp commerce capabilities. The web app has Telegram-authenticated catalogs such as `/api/v1/store` (Stars) and `/api/v1/card/store`, plus checkout routes that require a verified Telegram identity. These are not directly usable by an unverified WhatsApp sender.

The existing `/internal/telegram/mcp-proof` route is a read-only connectivity proof, not a commerce API. Do not reuse it for pairing, purchases, or settlement. The Telegram Gateway's `initData` validation does not verify the identity of a WhatsApp sender.

## 2. MVP scope: catalog + non-financial inquiry

- Receive inbound messages only after provider signature verification (Twilio is a candidate because outbound Twilio support already exists).
- Allowlist simple intents: `help`, `catalog`, `price <sku>`, `buy <sku>`.
- Return only published product data from the canonical Control Plane; never invent price, currency, availability, delivery terms, token allocation or ROI claims.
- `buy <sku>` creates only a non-financial inquiry/intent after the provider signature is verified and the canonical catalog/policy check passes. A linked SLH account is not required for a generic inquiry because it grants no private account access or purchase rights; any account-specific action, eligibility check, checkout or fulfillment requires separate verified account pairing. Tell the customer it is an inquiry, not a completed purchase.
- Keep outbound marketing broadcasts out of this MVP; require documented opt-in and an opt-out path.
- No payment, wallet mutation, Credits debit/credit, revenue posting, token mint/transfer, payment claim, payout or fulfilment in this phase.

## 3. Required architecture

`WhatsApp provider (signed webhook) → slh-api/routes/whatsapp.py → scoped service adapter → canonical Control Plane → WhatsApp response`

1. The Control Plane remains authoritative for canonical principal, permissions, product catalogue, prices/currencies, eligibility, feature flags and idempotency.
2. No cross-repository Python imports, direct access to the bot's `state/db.json`, local shadow roles, or local shadow financial ledger.
3. Use a dedicated least-privilege service identity/scope. Do not assume `SLH_MCP_BRIDGE_TOKEN` grants commerce permissions; the existing proof uses it only for a read-only proof. Do not add secrets to source control.
4. Fail closed on missing/invalid auth, unknown identity, ambiguous pairing, unavailable Control Plane, unpublished SKU, denied permission, missing idempotency key or unclear response.
5. Keep store handlers disabled by default. Checkout has a separate default-off flag.

## 4. Identity pairing

A contact row or imported phone number is not proof of ownership of an SLH account. Generic inquiry-only handling may use the provider-verified phone without linking an SLH account, but must not expose balances, private account data or account-specific eligibility. Pairing is required before any account-specific operation, checkout or fulfillment.

1. An authenticated user starts pairing from the canonical Telegram bot or authenticated Mini App.
2. Generate a cryptographically random, short-lived, single-use code; store only a hash, rate-limit attempts, and invalidate after use or expiry.
3. Validate the provider signature against the raw inbound request and canonical externally configured URL before parsing the message.
4. Derive the phone number only from the verified provider payload. Never trust a caller-supplied Telegram UID.
5. The canonical Control Plane validates the code and binds the phone to its canonical principal. All later requests re-resolve principal and permissions.
6. Unlinked, expired, reused, revoked or conflicting identities cannot access private balances or perform purchase actions.

## 5. Control Plane contracts

The first implementation draft is in [slh-bot PR #656](https://github.com/osifeu-prog/slh-bot/pull/656). It is **not merged or deployed**.

- `GET /internal/commerce/v1/whatsapp/catalog`: returns only products in the canonical Telegram Stars catalog, with customer-safe name/description, exact XTR price and `checkout_channel=telegram_stars`. It explicitly reports `payment_in_whatsapp=false`.
- `POST /internal/commerce/v1/whatsapp/intents`: accepts `provider=twilio`, a provider message ID, approved SKU, `intent=purchase_inquiry`, and `customer_confirmed=true`; returns an opaque inquiry ID and `inquiry_pending`. The Control Plane hashes the provider message ID for idempotency, returns the original record on identical replay, and rejects reuse of the same message ID for a different SKU.

Both routes require the dedicated `SLH_WHATSAPP_STORE_BRIDGE_TOKEN`, `SLH_WHATSAPP_STORE_PRINCIPAL_ID`, canonical `WHATSAPP_STORE_SERVICE` role (the configured principal ID is granted only `whatsapp.store`), and `WHATSAPP_STORE_ENABLED=1`. The route explicitly rejects OWNER/ADMIN/DEVELOPER roles even if they would otherwise have wildcard permissions. Keep the principal ID separate from the owner UID. They are disabled by default; do not configure or enable them in production until the code PR is reviewed and the adapter is ready.

The initial inquiry API intentionally does not identify a Telegram user or accept a caller-supplied UID. A separate short-lived, single-use Telegram-started pairing flow must be designed before any account-level access, checkout or fulfillment. Inquiry creation must never cause a wallet, ledger, revenue, token or payment mutation.

## 6. Inbound security and reliability

- Verify provider signature before any state change.
- Require provider message IDs and enforce database-level idempotency; duplicates cannot create duplicate inquiries or duplicate confirmations.
- Limit body size, per-sender rate, retries, supported intents and retained message metadata.
- Treat message text as untrusted input; never interpret it as shell, SQL, arbitrary commands, URLs to fetch or Control Plane instructions.
- Redact auth headers, tokens, pairing codes, full phone numbers and full message bodies from logs/errors.
- Do not expose admin contact/import/broadcast endpoints to customers.
- Existing invite/fraud/broadcast semantics must remain unchanged; marketing requires consent and opt-out.

## 7. Financial and release gates

- Keep `WHATSAPP_STORE_ENABLED=0` until the provider signature, identity pairing, catalog read and inquiry flow pass end-to-end tests.
- Keep `WHATSAPP_STORE_CHECKOUT_ENABLED=0` until a separate financial design and review authorizes it.
- BNB and TON remain unavailable while canonical settlement gates/evidence are blocked or closed. A historical smoke PASS alone is not checkout authorization.
- No production variables, DB, balances, wallets, settlement, gates or deployment should change as a side effect of this design PR.

## 8. Acceptance tests

1. Invalid/missing signature rejected before mutation.
2. Duplicate webhook produces at most one inquiry/confirmation.
3. Missing, expired, reused or mismatched pairing code cannot bind a phone.
4. Imported contact does not imply verified account ownership.
5. Control Plane outage, missing scope, denied permission, unknown SKU or ambiguous identity fails closed.
6. Catalog values are exclusively canonical response values; no fallback prices or payment rails.
7. Inquiry creates no wallet/ledger/revenue/token/payment mutation and never returns a paid/fulfilled receipt.
8. Closed BNB/TON gates prevent those payment rails being displayed or initiated.
9. Secrets and full phone/message contents are redacted.
10. Existing WhatsApp endpoints and existing regression tests remain unchanged/green.
11. Both flags default off; tests do not change production state.

## 9. Split implementation plan

This is a two-repository change and should not be delivered as one broad PR.

### PR A — `slh-bot` (canonical Control Plane)
- Confirm bridge route implementation and implement/reuse narrowly scoped identity-pairing, catalog-read and inquiry contracts.
- Add tests for pairing expiry/replay, catalog publication, permissions and intent idempotency.
- Do not expose the MCP proof endpoint as a mutation surface and do not add financial mutations.

### PR B — `slh-api` (WhatsApp adapter)
- Implement signed inbound webhook, parser allowlist, provider-message idempotency, rate limiting and scoped Control Plane client.
- Reuse existing contact/invite/audit tables only where semantics fit; never infer identity from contact import.
- Keep both feature flags off by default and checkout absent/disabled.

### Release
- Approve exact API schemas and least-privilege scope.
- Run CI/security review on each final head.
- Test signed webhooks in a non-production/provider-test environment.
- Enable only the inquiry storefront after explicit review; defer checkout until separately authorized.

## 10. Out of scope

No parallel SLH bot, role system, ledger, payment processor, custody, withdrawal, token minting, tokenomics changes, investment/ROI claims, arbitrary agent execution, production DB edits, manual balance corrections or financial-gate changes.
