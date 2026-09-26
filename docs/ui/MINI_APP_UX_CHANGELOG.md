# Mini App UX Integration — Changelog

## Restore points

| Ref | Purpose |
|-----|--------|
| Branch `backup/pre-ui-ux-2026-09-26` | Snapshot of `main` **before** UX merge |
| Branch `ui/design-system-v1` | Design system docs + Mini App UX |
| PR #221 | Review / merge vehicle |

Rollback:
```bash
git fetch origin
git checkout main
git reset --hard origin/backup/pre-ui-ux-2026-09-26
# or revert the merge commit on main after merge
```

Railway: redeploy previous successful deployment if needed.

## What the UX change is aiming for

1. **Bottom nav**: בית · ארנק · שוק · עוד (secondary screens in sheet)
2. **Home money strip**: TON deposit path + Stars purchase — primary conversion
3. **TON status copy**: human Hebrew for `TON_*` errors; no seed UI
4. **setNext**: prioritizes wallet binding then funding
5. **Design tokens**: `body.slh-ds` + overlay CSS

## Smoke after deploy

- [ ] Open Mini App from Telegram only
- [ ] Home shows credits + two CTAs
- [ ] Bottom «עוד» opens Academy / Control
- [ ] Wallet → אמת TON opens Connect modal
- [ ] No mnemonic fields
- [ ] Failed verify shows Hebrew hint (not only code)
- [ ] Stars /pay still opens bot flow

## Money path (product)

Flow intended:
1. Verify TON (MyTonWallet / Tonkeeper — not @wallet)
2. Deposit with memo **or** buy Credits via Stars
3. Use Credits in Market / Exchange / Academy

Binding remains required for TON settlement (server rule unchanged).
