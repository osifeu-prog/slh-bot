# SLH Incidents / Reconciliations

## RECON-240-20260919 — staking counter

Status: RESOLVED

Six locked positions totaling 240 SLH were proven to have corresponding staking debits in both the live ledger and the pre-reset `state/db.bak`. The wallet counter was 552 while the locked-position total was 792. The counter was reconciled to 792 with a zero-credit ledger metadata record.

Evidence referenced during investigation:
- `state/db.bak` from 2026-09-09.
- Matching staking debits for all six position IDs.
- `state/reconciliations.json` record `RECON-240-20260919`.

No new credits were created and no stake positions were changed.

## TOKEN_BALANCE_PROVENANCE — 2026-09-11

Status: OPEN / forensic

Known evidence identifies a successful `atomic_update` execution in the exec audit associated with creation of the 44M token-balance aggregate. Earlier direct-write attempts were blocked and a separate attempt failed. The exact economic authorization/source still requires documentation.

Until resolved:
- no mint
- no burn
- no redistribution
- no supply migration
- no compensating balance changes

## Legacy state-wipe history

The state-manager hardening and deploy verification addressed the destructive-write class: malformed/empty DBs are now refused and writes use atomic replacement. Historical state evidence remains preserved for audit.
