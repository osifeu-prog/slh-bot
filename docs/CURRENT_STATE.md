# SLH Current State

Updated: 2026-09-19

## Verified green items

- Canonical `state_manager.save_db` uses atomic temp-file replacement via `os.replace`.
- Anti-wipe validation rejects malformed DBs and empty user sets.
- A full runtime DB backup was verified before the state-manager hardening.
- Live DB and the safe backup matched for users, stake positions, ledger, and owner staking state at verification time.
- Owner staking counter was reconciled from 552 to 792 after six historical locked positions (240 SLH total) were proven by ledger debits.
- Reconciliation records the counter correction as zero-credit accounting metadata; no credits were minted.
- Mini App wallet reads and dashboard/exchange paths are live.
- The Mini App tokenomics request was fixed in source to send Telegram authentication headers.

## Current known gaps

- The Mini App tokenomics authentication fix is on `main` but its Railway deployment is currently `NEEDS_APPROVAL`; it is not yet verified live.
- Agent ↔ Device canonical binding is not yet proven; User→Agent and User→Device ownership exist.
- SLH Bot local state and SLH API/Postgres are still separate data planes.
- The authoritative Device Registry in `slh-api` must be mapped before introducing another store.
- Multiple Railway projects/services remain; legacy services must not be treated as production merely because they exist.
- Website + Mini App + AI intake + Bot Factory entry points still need one documented ownership/routing map.

## Token provenance incident

The 44M SLH token-balance provenance incident has been corrected and documented. Current bot balances were reconciled to zero and the historical issuance/correction records are preserved. No new mint/burn/redistribution is authorized as part of the integration work unless separately approved and backed by a documented provenance path.

## Release principle

Only verified, versioned, tested changes are promoted to public-facing release. Historical forensic fixes and data reconciliations must remain explicitly documented and must not be silently represented as product features.
