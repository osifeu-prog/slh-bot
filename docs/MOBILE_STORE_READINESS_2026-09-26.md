# SLH OS — MOBILE STORE READINESS
Updated: 2026-09-26

## Architecture decision
Create one canonical SLH OS mobile product.
Do not publish one app per Telegram bot/service.

Canonical application surface:
- SLH OS mobile client
- canonical API/control plane
- wallet/connectivity services
- commerce services
- Academy/rewards/agent surfaces
- Telegram handoff where appropriate

## Current Railway inventory
- slh-os-control-plane
  - slh-mcp
  - web
- slh-cloud-bot
  - slh-cloud-bot
- SLH_investor_wallet_bot
  - slh-bot
  - Postgres
- slh-guardian
  - gardian
  - Redis
  - Postgres
- slh-api
  - slh-api
  - slh-air-bot
  - Redis
  - Postgres
- TELEGRAM-BOT
  - Telegram_bot
  - Grafana
  - Prometheus
  - Redis
  - Postgres

These are an inventory, not a claim that every service should be exposed to mobile users.

## Store gates
### Android / Google Play
Before submission:
- Determine whether the shipped functionality is a cryptocurrency wallet/exchange or another financial feature.
- Complete the Play financial-features declaration accurately.
- Verify country-specific licensing/registration before targeting each country.
- For Israel, Google Play currently states specific licensing requirements for cryptocurrency exchanges and software wallets.
- Use an Organization developer account for financial products such as cryptocurrency software wallets/exchanges.
- Prepare privacy policy, terms, support, data handling and account deletion flows.
- Keep crypto settlement disabled in any build whose compliance/legal status is not established.

### iOS / App Store
Before submission:
- Use an Organization developer account for crypto wallet functionality.
- Verify exchange/transmission licensing and jurisdiction coverage.
- Digital purchases that unlock app functionality must follow Apple's in-app-purchase rules; do not assume Telegram Stars can be reused as an iOS billing rail.
- Provide in-app account deletion for accounts created in the app.
- Provide review access/demo mode and explain non-obvious financial/wallet functionality in App Review notes.
- Do not ship unreviewed ICO/crypto-securities functionality.

## Release architecture
1. Stabilize canonical web/Mini App behavior.
2. Define one API contract consumed by mobile and web.
3. Add native mobile authentication/deep-link handoff.
4. Integrate WalletConnect and injected wallets with platform-specific testing.
5. Separate:
   - account identity
   - wallet ownership binding
   - transaction detection
   - financial settlement
6. Build Android and iOS shells from the canonical client.
7. Add store-specific billing only where required.
8. Run internal/beta testing.
9. Prepare store declarations and compliance evidence.
10. Submit only after Gate A-E evidence is complete.

## Current Gate
Gate A — Connectivity:
- WalletConnect code: READY IN MAIN
- canonical Mini App URL: READY IN MAIN
- Origin diagnostics: READY IN MAIN
- Railway deployment: currently BUILDING for commit 7dde2226...
- manual Reown/WalletConnect Project Domain allowlist: still required
- real mobile wallet E2E: still required

## Next technical order
A. Finish WalletConnect mobile E2E.
B. Audit all active bot/service boundaries.
C. Choose canonical mobile frontend architecture.
D. Build mobile auth/session contract.
E. Build store-safe commerce abstraction.
F. Build Android beta.
G. Build iOS beta.
H. Review crypto/legal/store declarations before enabling regulated functions.

## Non-negotiable release rule
A store build must not expose or activate real-money settlement merely because the web Mini App works.
Each financial rail needs its own verified backend gate and compliance decision.
