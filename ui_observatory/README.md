# SLH UI/UX Observatory

A non-production Playwright harness for the existing `mini_app.html`.

## What it measures

- Primary Mini App navigation: Home, Wallet, Transfer, Buy, Staking, Alpha, Academy.
- Mobile layout overflow at an iPhone-class viewport.
- Interactive control names and form-label coverage.
- Serious/critical accessibility violations through axe-core.
- Visual evidence for each primary screen.
- Playwright trace/screenshot/video evidence when a test fails.

## Important boundary

The Observatory is evidence tooling only. It does not change balances, execute payments, enable BNB/TON claims, or deploy production code.

Backend APIs are mocked in the UI tests so a visual regression cannot accidentally depend on a user's financial state.

## Run locally

```bash
cd ui_observatory
npm install
npx playwright install chromium
SLH_UI_BASE_URL=http://127.0.0.1:8080/mini-app npm run test:ui
```

Start the existing Flask Mini App server separately:

```bash
python -m flask --app webapp run --host 127.0.0.1 --port 8080
```

The first run creates visual snapshots under `tests/**/*-snapshots/`. Commit those snapshots after reviewing them. Later runs compare against the committed baseline.

## Alpha usage

The Observatory should become a release-gate signal alongside backend/economy tests:

`UI navigation + accessibility + visual baseline + backend/economy evidence -> Alpha UI gate`

It must never be treated as proof that an on-chain deposit, payment, or ledger mutation occurred.
