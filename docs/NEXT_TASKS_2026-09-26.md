# SLH OS — NEXT TASKS
Updated: 2026-09-26 (Asia/Jerusalem)

## 0. Current blocker — WalletConnect
- [x] Canonical Mini App URL is `https://slh-cloud-bot-production.up.railway.app/mini-app-v4`.
- [x] WalletConnect SDK loads dynamically via ESM with UMD fallback.
- [x] BNB wallet binding remains separate from deposit settlement.
- [x] BNB settlement remains closed until end-to-end verification.
- [x] Added runtime Origin + WalletConnect URI diagnostics to the Mini App.
- [ ] Approve/deploy the latest three main-branch changes in Railway.
- [ ] In WalletConnect Dashboard, add the exact Mini App Origin used by Telegram to the project's allowlist.
- [ ] Test on desktop: Connect → BSC 56 → personal_sign → Verified.
- [ ] Test on mobile: Telegram → Mini App → WalletConnect → Trust/MetaMask Mobile → Connect → personal_sign → Verified.
- [ ] Only after successful tests: decide explicitly whether to open BNB deposit detection/settlement.

## 1. Wallet rails
- [ ] BNB: verify binding, chain switch, challenge expiry, replay/idempotency, confirmations and Treasury routing.
- [ ] BNB: validate native BNB deposit and SLH BEP-20 deposit end-to-end with a small controlled test.
- [ ] TON: re-test TON Proof/SignData path and keep TON native-only settlement rules explicit.
- [ ] Cross-chain: document which assets are supported, which are wallet-only, and which are settlement rails.
- [ ] Never mix on-chain balances with internal Credits.

## 2. Mini App / UX
- [ ] Remove stale links/cache versions after canonical URL is proven.
- [ ] Replace any UI copy that says “Crypto” where the specific product only supports Stars/Card.
- [ ] Add a visible “Connected / Verified / Settlement” state model for every wallet rail.
- [ ] Add a diagnostic panel that can be hidden behind an Owner-only switch after production verification.
- [ ] Confirm Telegram WebView behavior on Android and iOS.

## 3. Bot and service synchronization
- [ ] Inventory every active service/bot and assign one canonical role.
- [ ] One control-plane map: bot → API → Mini App → MCP → storage → deployment.
- [ ] One canonical public API/origin per surface; eliminate stale Railway domains.
- [ ] Verify bot polling uniqueness and leave intentionally disabled services disabled.
- [ ] Verify secrets/LLM readiness separately from wallet readiness.
- [ ] Keep `state/db.json` as runtime source of truth; do not reintroduce runtime DB tracking to Git.

## 4. Commerce
- [ ] Stars checkout: verify catalog, invoice, fulfillment and idempotency.
- [ ] Card checkout: verify provider, supported physical products and webhook/recovery path.
- [ ] Crypto checkout/deposits: separate payment acceptance from internal Credits settlement.
- [ ] Add transaction/audit views for Owner and support.

## 5. Alpha readiness
- [ ] Economy sanity.
- [ ] Wallet/connectivity smoke tests.
- [ ] Purchase smoke tests.
- [ ] Academy/paywall smoke tests.
- [ ] Referral/rewards smoke tests.
- [ ] GO/NO-GO evidence pack.

## 6. Google Play / App Store preparation
- [ ] Freeze the canonical web/PWA contract before packaging.
- [ ] Choose wrapper architecture (PWA/TWA for Android and WebView/Capacitor-style shell for iOS only after security review).
- [ ] Define deep links/app links and Telegram handoff behavior.
- [ ] Define permissions, privacy policy, Terms, support URL and account/data deletion flow.
- [ ] Prepare app icon, splash, screenshots and store metadata.
- [ ] Prepare Android signing key/keystore and iOS signing/distribution credentials securely.
- [ ] Test wallet connections outside Telegram WebView on real Android + iPhone devices.
- [ ] Submit internal/beta builds before public release.

## 7. Release gates
### Gate A — Connectivity
WalletConnect + injected wallet + TON Connect tested on real devices.

### Gate B — Identity
Telegram auth + wallet ownership challenge verified; no client-supplied UID trusted.

### Gate C — Money
Deposit detection, confirmations, Treasury routing, idempotency and credit mutation verified.

### Gate D — Commerce
Stars/Card flows verified with real test transactions where appropriate.

### Gate E — Mobile stores
Android/iOS builds pass review-oriented privacy, permissions, payments and deep-link checks.

## Working rule
Do not open a real-money settlement gate solely because the UI works.
Move a gate only after the corresponding end-to-end evidence is recorded.
