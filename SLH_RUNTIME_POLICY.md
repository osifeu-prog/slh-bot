# SLH OS RUNTIME POLICY

Date: 2026-08-06

Production runtime:
Railway is the permanent production environment.

Rules:
- Do not stop Railway service during recovery/debug.
- Railway remains the single Telegram polling owner.
- Local PowerShell is for diagnostics, audits and controlled fixes only.
- Avoid running bot_stable.py locally while Railway polling is active.
- EXEC workflow should return to Telegram bot control after stabilization.

Current state:
- Railway service: ONLINE
- Token handler migrated to wallet system.
- Custom handler loading verified.
- Telegram 409 conflicts indicate duplicate polling only.

Priority:
System stability > local testing.

