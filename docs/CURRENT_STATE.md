# SLH OS — CURRENT STATE (מקור אמת)

עודכן: 2026-09-26

## Runtime
- Production service: Railway project `slh-os-control-plane` / service `web`.
- Secondary runtime: Railway project `slh-cloud-bot` / service `slh-cloud-bot` (RUN_BOT=0, non-polling).
- Start command: `bash start_railway.sh`.
- Current verified production deployment: `5343328d-924b-4717-8a2b-73d79155a051`, commit `2824a8d60659a69aba9d77c496a0516cbf1fefe6`, status `SUCCESS` (2026-10-06).
- `/start` was re-verified by the owner on 2026-09-26 and returned the personal dashboard successfully.
- Control Center `/os` fix (PR #235) and Stars financial truth (#420) deployed successfully as of 2026-10-06.
- Production state volume is mounted at `/app/state`.

## Development rules
1. Every code change goes through a PR to `main`.
2. Runtime state under `state/` is not source code and must not be committed.
3. `/e` is read-only verification; container edits are not release artifacts.
4. Do not mark a feature LIVE or verified without runtime or on-chain evidence.
5. Financial, wallet, token, deposit, mint, transfer, and settlement changes require explicit verification before release.

## AI
- Gemini is configured but has recently returned HTTP 429 quota errors in production.
- Groq is configured but can enter application cooldown after provider failures.
- Ollama support exists in code and is active only when `OLLAMA_BASE_URL` is configured.
- `/os` still reports the older simplified state until PR #235 is deployed.

## Wallets / chains
- TON wallet binding exists in the Mini App and is handled separately from BSC.
- BNB wallet binding supports the existing injected-provider path.
- WalletConnect BNB support is prepared in PR #234; it is not merged and no production Project ID is configured.
- BSC Treasury `0x693db6c817083818696a7228aebfbd0cd3371f02` uses an EIP-7702 delegation visible on-chain. Controller identity and historical custody still require independent verification.
- No BSC or TON transaction was sent as part of the 2026-09-26 engineering and forensic work.

## Token / liquidity forensics
- SLH token owner is the Treasury address above.
- Observed on-chain state: total supply 111,186,328 SLH; Treasury balance 26,332,942.28 SLH.
- Observed SLH/WBNB PancakeSwap V2 pool reserves were approximately 3.14 SLH and 0.00000304 WBNB, so it must not be represented as a liquid market without further evidence.
- LP token holder identity is not yet established.
- No mint/burn/redistribution is authorized by this document.

## State data
- `state/db.json` is ignored by `.gitignore` but is still tracked in Git; it must be removed from repository tracking in a separate controlled change.
- `state_manager.load_db()` initializes an empty structure when the file is absent, and `save_db()` refuses malformed or empty-user writes.

## Public website
- Historical `/control-center.html` currently returns HTTP 404 in public verification.
- Current public repo contains `control.html`, which uses a client-side `localStorage` password gate; that is not a substitute for server-side authorization.
- The connected website repository is read-only for the current GitHub connection, so website security changes cannot be pushed from this connection.

## Release gates
- Production bot stability: verified for `/start`.
- Control Center runtime observability: merged as PR #235; Railway deployment still requires approval.
- WalletConnect BNB: pending merge and production Project ID configuration.
- Treasury security: controller ownership and LP ownership unresolved.
- Customer-facing BNB/TON deposits: availability must be verified from runtime gate and custody path; environment-variable names alone are not evidence.

## Source-of-truth principle
This file records verified state and unresolved items. Historical documents are subordinate when they conflict with runtime, repository, or on-chain evidence.