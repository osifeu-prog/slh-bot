# AGENT RULES - SLH OS
CONSTANT RULES FOR ANY AI AGENT WORKING ON THIS PROJECT.
These apply regardless of session, always active, never optional.

1. One step at a time. Never batch multiple untested changes.
2. Confirm plan with owner before writing code.
3. Never rebuild from scratch. Fix or restore from backups.
4. Always py_compile before any restart.
5. Owner works from Android Termux only, no file transfer, mobile-first, heredoc/cat delivery only.
6. Never print or expose full secrets/tokens in any output. Prefix only, 6-10 chars.
7. Production is Railway. Termux is dev only, never run bot in parallel with Railway.
8. Do not conclude a session or suggest a new chat unless owner explicitly asks.
9. Read SLH_AGENT_HANDOFF.md and run /journal_read in Telegram before touching code.
