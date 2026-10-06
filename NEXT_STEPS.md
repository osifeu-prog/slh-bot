# SLH Next Steps

Current stable:
- Bot running: @SLH_Test_bot (Railway: slh-os-control-plane/web, ONLINE)
- Loader working
- CI working (repo public)
- Ruleset active (Protect main)
- Commit: 35e76bda

## Tomorrow (2026-10-07)

### PRIMARY — Bot Shop design
1. Review existing: core/bot_factory.py, core/bot_registry.py, handlers/stars_store.py
2. Define template catalog (which templates to sell first?)
3. Define managed-bot pricing model
4. Write handlers/bot_shop_handler.py — starting with /bot_shop listing
5. Extend store/items.json with bot_template items

### SECONDARY
6. Rotate personal access token (minimal scopes: repo, workflow, read:org)
7. Test @SLH_Test_bot access control with second user
8. Monitor Release Evidence for 24h (expect 1 success + N cancelled)

### DO NOT
- Do not modify architecture before spec is written
- Do not push directly to main
- Do not touch filter-repo again without a backup tag