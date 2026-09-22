# SLH System Census — 2026-09-22

## Purpose
Canonical synchronization snapshot for the SLH project family. This document is intentionally read-only/audit-oriented: it records what the connected GitHub and Railway integrations can currently see and the current consolidation direction.

## Access boundary

### GitHub
- Repositories visible through the connected GitHub installation: **17**
- Repositories with reported push access: **1**
- Writable/canonical engineering repository: **osifeu-prog/slh-bot**
- Other visible repositories are currently read-only through this connector.

Visible repositories:
1. osifeu-prog/SLH_PROJECT_V2
2. osifeu-prog/osifeu-prog.github.io
3. osifeu-prog/ME
4. osifeu-prog/telegram-bot
5. osifeu-prog/investor-landing
6. osifeu-prog/Tax_Free_world_bot
7. osifeu-prog/GATE_BOTSHOP
8. osifeu-prog/slh-master-bot
9. osifeu-prog/SLH-Lab
10. osifeu-prog/slh-claude-bot
11. osifeu-prog/nifti-bot-
12. osifeu-prog/SLHADMIN
13. osifeu-prog/SLH.co.il
14. osifeu-prog/slh-trading-bot
15. osifeu-prog/slh-bot
16. osifeu-prog/DAVIDANDFARID
17. osifeu-prog/TECH

### Railway
- Visible workspace: **osifeu-prog's Projects**
- Railway projects visible: **10**
- Services visible: **35** (including databases/caches/monitoring services)

Projects:
1. endearing-amazement
2. slh-cloud-bot
3. nifti-bot
4. SLH_investor_wallet_bot
5. Tax_Free_world_bot
6. TELEGRAM-BOT
7. slh-guardian
8. diligent-radiance
9. slh-api
10. dazzling-unity

## Canonical production path currently established

**GitHub main → Railway endearing-amazement/web → Telegram @Me_ad_main_bot → Mini-App → Stars → Credits → Academy → Agents → Staking**

Known canonical production repo/commit:
- Repo: osifeu-prog/slh-bot
- Branch: main
- Commit: 96990e1aae5d52da4d01221868514eaa2c464ce1
- Main feature at this snapshot: centralized Telegram Stars pricing (#146)

Known canonical Railway web service:
- Project: endearing-amazement
- Service: web
- Start: bash start_railway.sh
- Healthcheck: /health
- Domain: web-production-22f28.up.railway.app
- Restart policy: ALWAYS
- Volume: /app/state
- Replica region: us-west2

Known MCP service:
- Project: endearing-amazement
- Service: slh-mcp
- Start: python -m uvicorn slh_mcp.server:app --host 0.0.0.0 --port 8080
- Healthcheck: /health
- Domain: slh-mcp-production.up.railway.app
- Last known deployment at audit time: SUCCESS

Known non-polling cloud worker:
- Project: slh-cloud-bot
- Service: slh-cloud-bot
- Same GitHub repo/main
- RUN_BOT=0
- Purpose: must not compete with the canonical Telegram polling runtime.

## Consolidation direction

### KEEP / canonical
- osifeu-prog/slh-bot main
- Railway endearing-amazement/web
- Railway endearing-amazement/slh-mcp
- slh-cloud-bot only if it remains a deliberate non-polling control/worker service
- Known-good backups/archives until their contents are explicitly captured elsewhere

### MERGE-CANDIDATE / requires evidence before any deletion
- SLH_PROJECT_V2 vs slh-bot
- SLH.co.il vs osifeu-prog.github.io
- ME vs slh-master-bot vs telegram-bot
- slh-api vs API functionality now inside slh-bot
- old MCP branches/projects vs the deployed slh-mcp
- duplicate Mini-App, Academy, Stars, staking, economy, agent, and control-plane branches

### SEPARATE PRODUCT / do not merge merely for cleanup
- nifti-bot / nifti-bot-
- SLH_investor_wallet_bot
- Tax_Free_world_bot
- GATE_BOTSHOP
- slh-trading-bot
- other independently deployed products unless dependency analysis proves otherwise

### REVIEW BEFORE ARCHIVE
- diligent-radiance services
- TELEGRAM-BOT stack
- slh-guardian stack
- slh-api stack
- dazzling-unity / SLH_PROJECT_V2 service
- old website/API/AI services

A prior failure history exists for some AI/API services, but current service configuration should be rechecked before declaring them dead.

## Important safety rule for cleanup
Do not delete repositories, Railway projects, databases, volumes, or branches merely because their names look old or duplicated.

For each candidate, establish:
1. Is it deployed?
2. Which repo/commit supplies it?
3. Does another active service depend on it?
4. Does it own persistent data?
5. Does it contain unique functionality not present on main?
6. Is it a backup that may be needed for rollback?
7. Can it be reproduced from canonical main?

Only then classify as ARCHIVE or DELETE-CANDIDATE.

## Current branch situation
- slh-bot currently exposes a very large historical branch inventory (194 branches observed).
- Open PR backlog was cleaned to zero in the preceding audit; many PRs were already merged/obsolete.
- Branch deletion has NOT been performed by this census.
- Historical branches must be classified by commit relationship before removal.

## Known code-level cleanup targets
These are audit targets, not deletion instructions.

### Handler loader
handlers/loader.py currently imports a very large handler surface, including legacy/suspicious names such as:
- brief_legacy
- legacy_wallet
- junk
- test
- sandbox
- complete
- diagnostic
- guide
- tutorial
- viewfile
- devsetup
- refresh
- autoexec
- recovery

Before removal, verify imports, routes, tests, runtime references, and production behavior.

### Reconciler
core/reconciler.py currently mutates state and filters tasks containing terms such as "test" or "lifecycle". It also repairs missing wallet fields.

This deserves an explicit safety review before it is ever run as an automatic cleanup mechanism.

## Golden-path product state
Known implemented/runtime-verified areas include:
- Telegram onboarding: /start → /join → profile/personal agent → Academy
- Academy course bitcoin_mastery
- Telegram Stars invoice generation
- Stars → Credits fulfillment path with idempotency/reconciliation logic
- Credits → Store
- Store fulfillment architecture
- Mini-App Telegram initData validation and wallet read APIs
- staking/unstaking lock enforcement
- agent registry/state store and governed mission execution architecture
- exchange read endpoints

Important remaining verification gaps include:
- real Telegram Stars payment E2E, not just invoice generation
- final paid-capability mapping
- full end-to-end alpha gate
- systematic dependency mapping across the 17 repos and 10 Railway projects
- branch-by-branch consolidation evidence

## Sync instructions
Recommended local workflow:

```bash
git fetch origin
git switch docs/system-census-20260922
git pull --ff-only origin docs/system-census-20260922
```

Then inspect:
- docs/SYSTEM_CENSUS_2026-09-22.md
- docs/SYSTEM_CENSUS_2026-09-22.json

Do not use this document as permission to delete anything. It is the shared map from which cleanup decisions should be made.

## Snapshot provenance
Captured from the connected GitHub/Railway integrations during the 2026-09-22 consolidation audit. Configuration values/secrets are intentionally excluded.
