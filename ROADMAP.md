# SLH OS — Current Roadmap

> Last reconciled: 30 September 2026
> Scope: verified runtime/code work only. Settlement gates remain fail-closed.

## ✅ Current baseline

- Canonical repository: `osifeu-prog/slh-bot`
- Production bot runtime: Railway `slh-cloud-bot`
- Current verified production deployment: `82d60dc9-d973-4b5e-a2c2-a2bf74ec88bd` — SUCCESS
- Control Plane is separate from the bot runtime.
- Control Plane services `web` and `slh-mcp` are independently deployed.
- Persistent runtime state is under `/app/state`; `state/db.json` remains the application source of truth.
- Alpha is OPEN in the current application state.
- BNB settlement remains CLOSED.
- TON settlement must remain closed unless its runtime gate explicitly reports open; no opening is performed by this roadmap.
- Telegram Stars are product-payment rails; they are not treated as crypto settlement.

## ✅ Recently completed / merged

- Exact BNB settlement amount handling preserves integer wei through settlement.
- TON Mini App binding uses the canonical proof domain `slh-nft.com`.
- TON Mini App includes transaction-check UI and respects the deposit gate.
- Added TON Mini App contract tests.
- Runtime command surfaces were aligned for Alpha, TON claim aliases, Admin shortcuts and the `/os` menu.
- Gateway output is chunked to stay below Telegram message limits.
- `/e` normalizes pasted command descriptions to canonical commands.
- `/help` is generated from runtime-registered handlers and hides owner-only commands from regular users.
- `/allcommands` is owner-only and uses the same runtime command registry.
- Wallet-binding and vault-regression paths remain guarded by CI.
- UI workflow now installs Chromium runtime dependencies without requiring root access.

## 🟡 Active work

### PR #311 — TON Mini App + command-surface cleanup

Current HEAD:
`6a87fc6834236d5b6d7607435c5d4df2d0769a24`

Required before merge:
- All required CI checks green on the same HEAD.
- UI/UX Observatory must start successfully on the self-hosted runner.
- No production deployment until the PR is merge-ready.

### Command surface verification

After deployment, verify at minimum:
- `/help`
- `/allcommands`
- `/os`
- `/admin`
- `/alpha`
- `/ton_claim`
- `/gateway`
- `/e alpha_status — canonical Alpha evaluation`
- `/monitor_list`, `/monitor_status`, `/monitor_logs`

### Read-only architecture cleanup

- Keep `/project`, `/unified_map`, `/control` aligned with verified Railway topology.
- Keep runtime command catalogs sourced from actual registered handlers rather than stale hand-maintained lists.
- Continue distinguishing canonical bot runtime, Control Plane web, MCP, API and legacy/external stacks.

## 🔒 Settlement gates

BNB and TON settlement opening are separate release activities. They require their own empirical proof, reconciliation and idempotency evidence and are not part of PR #311 deployment.

## 🧪 Release rule

No merge/deploy is considered complete until the target commit is identified, CI evidence matches that exact commit, Railway deployment reports SUCCESS, and the live runtime reports the deployed commit.
