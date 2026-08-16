# SLH OS — TOMORROW HANDOFF
Date: 2026-07-27

## MISSION
Closure / Production Readiness.
NO NEW FEATURES.
NO ARCHITECTURE CHANGES.
ONE SOURCE OF TRUTH.
ONE TEST.
ONE FIX AT A TIME.

## MANTRA
OBSERVE → PROVE → FIX → TEST → FREEZE

## VERIFIED
- /ask active through advanced_ask_handler
- Local answer works
- /ask "כמה סוכנים" returns 4
- Duplicate/Cooldown protection exists
- Local test does not send data to LLM
- Static handler audit completed
- No syntax errors in audited result
- Bot token exposure is a security issue and must be rotated if not already done

## OPEN — PRIORITY ORDER
1. OWNER IDENTITY
   config/db: 8789977826
   core/identity.py: 972500000001
   Choose ONE source of truth and verify all permission paths.

2. JOIN FLOW
   Trace:
   Telegram ID → /join → handler → DB → role → permissions
   Verify OWNER behavior.

3. ASK ROUTER
   Map actual runtime path:
   /ask → local answer → AI Guard → provider → LLM → fallback
   Do not rewrite before proving the active path.

4. AGENTS UTF-8
   Investigate:
   'utf-8' codec can't decode byte 0x95
   Identify exact file and encoding before modifying.

5. COMMAND REGISTRY
   Produce active command list and owner handler for each.

6. SMOKE TEST
   Test only after identity and routing are understood.

7. BACKUP → REGRESSION → FREEZE

## STOP RULE
If a test fails:
STOP.
READ THE ERROR.
MAKE ONE SMALL FIX.
RUN THE SAME TEST AGAIN.

## DO NOT
- Do not add agents.
- Do not create another router.
- Do not rewrite architecture.
- Do not blindly replace code.
- Do not paste bot output into /exec.
- Do not use /exec to run prose or Telegram responses.

## FIRST COMMAND TOMORROW
pwd
git status --short
git log -1 --oneline
