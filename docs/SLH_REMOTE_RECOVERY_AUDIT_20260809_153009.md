# SLH OS Remote Recovery Audit

**Captured:** 2026-08-09T15:30:10.6653708+03:00
**Source:** PowerShell + Railway CLI
**Primary project:** endearing-amazement
**Primary service:** web

## Current State

The primary SLH Railway service is online and deployed from osifeu-prog/slh-bot.

The primary runtime is ot_gateway.py and uses:

- RUN_BOT=1
- Telegram polling
- Railway volume /app/state

## Confirmed Incident

The primary service produces Telegram:

409 Conflict: terminated by other getUpdates request

This confirms that another process/runtime is polling the same Telegram bot.

## Remote Inventory

Known Railway projects examined:

- endearing-amazement
- slh-cloud-bot
- SLH_investor_wallet_bot
- nifti-bot
- resilient-love
- TELEGRAM-BOT
- diligent-radiance
- slh-guardian
- Tax_Free_world_bot
- slh.co.il
- slh-api
- dazzling-unity

## Important Findings

### Active/confirmed polling signals

- endearing-amazement / web — confirmed 409 conflict
- diligent-radiance / TON-MNH-bot — active getUpdates
- slh-guardian / gardian — infinity_polling signal
- SLH_investor_wallet_bot / slh-bot — repeated Telegram Unauthorized

### Security Finding

A collected Railway log contained a raw Telegram bot token inside a Telegram API URL.

The token value is intentionally NOT stored in this audit.

Any token exposed through logs/chat must be rotated before public release.

## Secret Handling Rule

This inventory stores:

- presence/absence
- service association
- operational status
- non-reversible fingerprint when necessary

It does NOT store:

- raw BOT_TOKEN
- API keys
- passwords
- private credentials

## Recovery Strategy

The long-term objective is not deletion of the legacy Railway projects.

They are treated as recoverable SLH assets.

Future SLH control-plane functionality should allow:

1. discovery
2. identity/fingerprint matching
3. health assessment
4. controlled activation
5. controlled shutdown
6. conflict detection
7. state preservation
8. migration/integration
9. audit logging

## Immediate Priority

Do NOT activate legacy bots yet.

First eliminate the confirmed duplicate Telegram polling conflict on the primary SLH bot.

After primary SLH polling is stable, proceed with controlled recovery/integration of the remaining projects.

## Integrity Principle

No project should be considered disposable merely because it is currently offline.

Existing projects are treated as potential historical modules/assets of the SLH ecosystem until explicitly classified otherwise.

---

## Documentation Integrity Check

**Timestamp:** 2026-08-09T15:31:23.7352682+03:00

- Remote inventory located and validated.
- Recovery audit located and validated.
- Pre-conflict checkpoint located and validated.
- No raw Telegram token pattern detected in recovery audit.
- .env added to local Git ignore policy.
- *.bak added to local Git ignore policy.
- __pycache__/ added to local Git ignore policy.
- *.pyc retained/protected.
- No runtime was stopped.
- No Railway deployment was changed.
- No BOT_TOKEN was modified.
- No legacy project was activated.

**Next controlled operation:** exact Telegram token ownership/fingerprint matching before any runtime shutdown.

---

## Exact Telegram Token Ownership Scan

**Timestamp:** 2026-08-09T15:32:03.3645092+03:00

- Primary: endearing-amazement/web
- Primary token identified by SHA-256 fingerprint only.
- Raw BOT_TOKEN values were not printed.
- Raw BOT_TOKEN values were not stored.
- All inventoried Railway projects were scanned.
- Exact token matches were identified by fingerprint.
- No Railway service was stopped.
- No BOT_TOKEN was changed.
- No legacy project was activated.

### Exact Primary Token Matches

- NONE FOUND

**Safe ownership map:** docs/SLH/SLH_TELEGRAM_TOKEN_OWNERSHIP_MAP.json

**Next controlled action:** determine which exact matching runtime is the conflicting poller, then stop only the confirmed duplicate.
