# SLH OS Control Tower

Persistent operator surface for SLH OS from Windows PowerShell.

## Canonical boundaries

- GitHub \`osifeu-prog/slh-bot@main\` — versioned code, review, CI and release history.
- Railway — live deployments, runtime topology and infrastructure state.
- \`state/db.json\` on the Railway Volume — current bot data plane.
- \`slh-api\` / Postgres — separate API/data plane.
- \`C:\Users\USER\slh_agent.py\` — local PC agent / operator node.

The Control Tower is an operator surface, not a second source of truth.

## Targets

| Alias | Railway project | Service | Role |
|---|---|---|---|
| \`main\` | \`slh-cloud-bot\` | \`slh-cloud-bot\` | Telegram/Main runtime |
| \`web\` | \`endearing-amazement\` | \`web\` | Web/Mini App runtime |
| \`api\` | \`slh-api\` | \`slh-api\` | Canonical API/auth/data plane |

All identifiers live in \`config/slh_control_targets.json\`.

## Commands

\`\`\`text
slh
slhstatus
slhmap
slhwatch
slhjournal
slhtasks
slhsync
slhpc
slhlogs
slhdeploycheck
slhvarnames
slhuse main
slhuse web
slhuse api
slhpull -Force
\`\`\`

## Safety

Read-only by default.

The Control Tower never uses \`railway up\` for release work. Code changes travel through GitHub review/CI and Railway's source deployment path.

Secret values are never printed.

Credits, staking, deposits, exchange state, token balances and other financial state are not mutated by these commands.

## Release workflow

1. \`slhstatus\`
2. Make the code change in a branch.
3. Commit and push.
4. Open/review/merge the GitHub PR.
5. Verify Railway reaches \`SUCCESS\`.
6. \`slhdeploycheck\`
7. \`slhwatch\`
8. Record the result in the persistent handoff/journal.

## Return after a break

\`\`\`powershell
cd "$env:USERPROFILE\slh-bot-clean"
slh
slhsync
slhmap
\`\`\`

## PC heartbeat

Device: \`PC_Osif2\`

Topic: \`slh/device/PC_Osif2/heartbeat\`

The heartbeat secret remains outside Git under the user profile. The Control Tower only checks presence/length.
