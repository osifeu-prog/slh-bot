# SLH OS Control Tower

Persistent Windows PowerShell operator surface for SLH OS.

## Canonical boundaries

- GitHub osifeu-prog/slh-bot@main: versioned code, review, CI and release history.
- Railway: live deployment/runtime/infrastructure truth.
- Railway Volume /app/state: bot data plane including state/db.json.
- slh-api / Postgres: separate API/data plane.
- %USERPROFILE%\\slh_agent.py: local PC agent.

PowerShell is an operator surface, not a competing source of truth.

## Commands

```text
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
slhredeploy -Force
slhpull -Force
```

## Safety

Read-only by default.

The Control Tower never uses railway up for release work. Code changes travel through GitHub PR/CI and the normal Railway source deployment path.
Secret values are never printed.
Credits, staking, TON, BNB, exchange state and token balances are not mutated by this tool.

## Recovery

```powershell
cd "$env:USERPROFILE\\slh-bot-clean"
slh
slhsync
slhmap
```

## PC heartbeat

Device: PC_Osif2
Topic: slh/device/PC_Osif2/heartbeat
The heartbeat secret remains outside Git. The Control Tower only reports presence/length.