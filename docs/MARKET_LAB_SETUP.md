# SLH Market Lab — Setup and safety boundary

## What the feature does

- Serves `/market-lab`, an informational market heatmap for a fixed, allowlisted set of broad-market and sector ETFs.
- Reads quotes through the server-side Twelve Data API adapter in `core/paper_market.py`.
- Offers a browser-local watchlist and paper portfolio. Simulated positions are stored in that browser's local storage and are not written to SLH financial ledgers.
- Does not connect to a brokerage account, submit orders, access wallet keys, move funds, or open any SLH financial gate.

## Provider setup

1. Create/authorize an account with the market-data provider and ensure its plan/license allows the coverage and display use required by the application.
2. Add `TWELVEDATA_API_KEY` as a server-side Railway variable for the Web service only.
3. Never put the key in HTML, JavaScript, a public query string, Telegram messages, GitHub, or browser local storage.
4. Test `GET /api/public/market-heatmap` in a non-production environment first. If the provider rejects batch quotes or a requested symbol is not entitled, the UI must show partial/unavailable data rather than fill missing tiles with invented prices.
5. Verify actual timestamps/delay and attribution against the account's provider plan and license before displaying market data publicly.

The adapter batches a fixed allowlist, uses a server-side Authorization header, has a short in-memory cache, suppresses raw provider error bodies, and returns only normalized price/change fields plus provider-reported timestamps.

## Safety and interpretation

- The heatmap classifies relative price movement only; a daily gain is not a buy signal.
- The paper portfolio is client-side simulation, not a record of owned assets and not a financial account statement.
- No trade, payment, wallet, deposit, withdrawal, Exchange, BNB, TON, or Stars execution path is called by the market-lab routes.
- Missing configuration or unavailable quotes fail closed; no static values masquerade as live market prices.
- Public market-data display may be subject to provider licensing, exchange entitlements, and delay requirements. Confirm those before enabling the provider key in production.
