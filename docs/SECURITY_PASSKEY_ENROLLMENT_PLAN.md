# SLH Spark Passkey / Biometric Enrollment — Implementation Gate

Status: design plan only. This document does not implement or enable passkey enrollment.

## User experience
Add a dedicated “הגדרת כניסה ביומטרית / Passkey” card to Mini App → Settings. The primary action should be “הגדרה ואימות במכשיר”. The UI must explain that the operating system may use fingerprint, face recognition, or the device PIN, depending on device configuration. The app cannot read, inspect, or calibrate the fingerprint sensor itself.

The flow should show distinct states: unsupported browser/device, not enrolled, registration in progress, enrolled, verification successful, cancelled, and recoverable error. Include “בדיקת אימות” and a clear “הסרת Passkey” flow, with confirmation and an appropriate re-authentication requirement.

## Security model
- Use WebAuthn / FIDO2 Passkeys. Never collect, upload, or store fingerprint images, templates, biometric samples, or device PINs.
- Preserve Telegram Mini App `initData` server verification as the identity/session baseline. A passkey must not silently bypass Telegram auth or be presented as a replacement for Telegram authentication in this first release.
- Bind each credential to the server-verified Telegram UID only; never trust a client-supplied UID.
- Use short-lived, single-use, cryptographically random registration/authentication challenges. Store and consume challenges server-side, with expiration and replay protection.
- Verify attestation/assertion challenge, exact configured origin, RP ID, credential ID, signature, user presence and user verification on the server. Reject malformed payloads and unknown credentials fail-closed.
- Store only the minimum credential record needed (credential ID, public key, signature counter/backup metadata, creation/last-used timestamps); never store private keys or biometric material.
- Apply CSRF/origin checks, request size limits, per-user/IP rate limits, generic error messages, and security audit events without logging assertions, challenges, initData, or credential secrets.
- Define recovery/removal behavior before treating a passkey as an account recovery factor. Do not lock a user out of the existing Telegram-authenticated flow if passkeys are unavailable.

## Blocking prerequisite: canonical persistence
Issue #748 documents two Railway services with distinct persistent volumes while the Web service serves Mini App routes and reads local state. Passkey credential records and one-time challenges must have a single authoritative persistence path. Do not deploy credential enrollment until the canonical state/API decision is implemented and verified. Do not copy/merge production `db.json` files as a shortcut.

## Required implementation and verification
1. Resolve and document the authoritative persistence/API for credential records and one-time challenges.
2. Pin and review a maintained server-side WebAuthn verification library; do not implement cryptographic verification manually.
3. Add authenticated registration-options and registration-verification endpoints, plus authentication-options and assertion-verification endpoints if/when passkey step-up is enabled.
4. Add the Mini App Settings card through a small isolated UI module; do not alter financial gates or wallet/ledger behavior.
5. Test valid and invalid challenges, expired/replayed challenges, origin/RP ID mismatch, invalid signatures, user-verification requirements, cross-user credential binding, duplicate credential IDs, malformed/oversized requests, unsupported browsers, cancellation, and no raw biometric material in API/database/log output.
6. Run SLH CI, Full Regression, Bot Vault Regression, and applicable auth/service-boundary checks on the exact final commit.
7. Keep the PR draft until security review and canonical-persistence evidence pass. No production deployment or authentication-policy change is authorized by this plan.

## Acceptance criteria
- A user can start registration from the Settings button and complete the platform authenticator prompt.
- The server verifies the WebAuthn response and persists the credential against the authenticated Telegram identity in the canonical store.
- The UI accurately describes the platform prompt and does not promise fingerprint-only support.
- All failures are fail-closed, recoverable, and do not reveal sensitive data.
- Existing Telegram Mini App auth remains unchanged; no financial routes, balances, ledger, deposits, withdrawals, exchange gates, or signing paths change.
