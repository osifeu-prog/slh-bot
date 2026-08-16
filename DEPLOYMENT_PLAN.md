# SLH UNIFIED DEPLOYMENT PLAN

## TARGET STATE
- Single bot entry point OR unified kernel entry
- Railway deployment
- Telegram control layer
- No Termux dependency except bootstrap

## PHASE 1
- Validate bot + kernel compatibility
- Remove duplicate runtimes

## PHASE 2
- Move runtime to Railway
- Inject BOT_TOKEN via env

## PHASE 3
- Enable:
  - /agents
  - /memory
  - /audit
  - /restart

## PHASE 4
- Optional: merge slh_clean + kernel into single runtime
