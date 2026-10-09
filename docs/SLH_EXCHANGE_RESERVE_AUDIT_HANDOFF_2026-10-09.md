# SLH Exchange Reserve Accounting — Handoff
**Updated:** 2026-10-09  
**Repository:** `osifeu-prog/slh-bot`  
**Audit branch:** `fix/exchange-slh-reserve-accounting`  
**Scope:** Read-only code investigation and handoff. No production changes, merges, deployments, transactions, or gate changes.

## Executive summary
A code-level accounting inconsistency is confirmed in the exchange SLH reserve path. `reserve_in_db()` documents that it moves spendable SLH into escrow, but it increments `exchange_reserved_slh` without reducing `live_token_balance`. The canonical invariant checker allows this state because it checks `live_token_balance <= token_balance` and `exchange_reserved_slh <= live_token_balance`, rather than ensuring available plus reserved is backed by total ownership. This can leave SLH that is already reserved for an open sell order appearing spendable.

The cancellation tests also encode conflicting assumptions: one fixture begins with total=100, live=60, reserved=40 (which implies live excludes escrow), while the reserve unit test leaves live=100 after reserving 40. This needs a deliberate semantic decision and consistent tests before code changes.

## Evidence inspected
- `core/slh_distribution.py`
  - `reserve_in_db()`: validates available balance, keeps `live_token_balance` unchanged, increments `exchange_reserved_slh`.
  - `settle_reserve_in_db()`: subtracts settled amount from seller total, live balance, and reserve; credits buyer total/live.
  - `release_reserve_in_db()`: reduces reserve but leaves seller live balance unchanged.
  - All three operations append canonical entries to `slh_token_ledger` with event IDs.
- `handlers/exchange_handler.py`
  - `_place()` creates sell order and calls `reserve_in_db()` within the atomic update path.
  - `_match()` calls `settle_reserve_in_db()` for matched quantity.
  - `_assert_invariants()` checks open sell-order reserves against wallet reserve totals, but not `live_token_balance + exchange_reserved_slh <= token_balance`.
  - `/cancel` uses `release_reserve_in_db()`.
- `handlers/webapp_data_handler.py`
  - Mini App sell orders converge on `_place()`; Mini App cancellation uses `release_reserve_in_db()` and then `_assert_invariants()`.
- `tests/test_slh_exchange_settlement.py`
  - Reserve test checks supply and replay safety, but does not assert that available live balance falls when reserve is created.
  - Settlement test checks total balances/reserve and supply, but not available-plus-reserved backing.
  - Cancel test begins with live=100 and reserved=0; it does not assert the expected return from an already-reduced available balance.
- `tests/test_webapp_exchange_cancel.py`
  - Cancellation fixtures begin with total=100, live=60, reserved=40 and expect cancellation to leave live=60 while reserve becomes 0. Under the stated semantics (“available” and “reserved” are separate), cancellation should restore live to 100. The fixture/expectation needs reconciliation with the canonical ledger model.

## Example invariant to validate
For the model in which `live_token_balance` is spendable and `exchange_reserved_slh` is escrow:
- Before reserve: total=100, live=100, reserved=0.
- After reserve 40: total=100, live=60, reserved=40.
- After settlement of 25 from that reserve: total=75, live=60, reserved=15.
- After cancellation/release of the remaining 15: total=75, live=75, reserved=0.

These are target semantics for tests, not observed runtime results. A core invariant should ensure available and reserved balances are jointly backed by total ownership; additionally the reserve amount must match open sell-order reserves.

## Next steps (in order)
1. Read every call site of `reserve_in_db`, `settle_reserve_in_db`, and `release_reserve_in_db`; verify migration/legacy wallet semantics and all readers of `live_token_balance`.
2. Decide and document the single meaning of `live_token_balance` (spendable excluding escrow is the current stated contract).
3. Add focused unit tests for reserve, partial settlement, cancellation after partial fill, idempotent replay, event-ID conflict, insufficient balance, and attempted double-spend while an order is open.
4. Ensure tests fail against the current implementation and pass after a minimal fix. Add the stronger balance invariant only after confirming existing legacy data is compatible.
5. Run the focused tests, then full regression/CI. Report exact commit SHA and workflow results.
6. Review changes in a PR. Do not merge or deploy until the diff, tests, and impact on existing open orders/state have been reviewed.

## Safety / production status
- This audit has not changed source code or production state.
- No tests were executed in a local runtime during this inspection.
- Earlier reported CI success is not proof this exact edge case is covered.
- Exchange read-only check previously reported `public_gate=OPEN` and readiness PASS, but that is not a substitute for these accounting tests.
- BNB deposit gate remains CLOSED according to the latest user-provided `/check_bnb` output. Do not open settlement/deposit gates as part of this audit.
- Do not place live orders or perform real-money/on-chain operations for verification. Use isolated test state only.

## Desktop/mobile continuation
The durable source of truth for this audit is this file on branch `fix/exchange-slh-reserve-accounting`, together with the source and tests linked below. GitHub branch updates are the shared work artifact; two separate ChatGPT conversations do not automatically share live internal reasoning. To continue on desktop, open this same ChatGPT conversation if possible. If using a new conversation, paste the “Resume prompt” below and the current branch/file link.

- `core/slh_distribution.py`: https://github.com/osifeu-prog/slh-bot/blob/fix/exchange-slh-reserve-accounting/core/slh_distribution.py
- `handlers/exchange_handler.py`: https://github.com/osifeu-prog/slh-bot/blob/fix/exchange-slh-reserve-accounting/handlers/exchange_handler.py
- `tests/test_slh_exchange_settlement.py`: https://github.com/osifeu-prog/slh-bot/blob/fix/exchange-slh-reserve-accounting/tests/test_slh_exchange_settlement.py
- `tests/test_webapp_exchange_cancel.py`: https://github.com/osifeu-prog/slh-bot/blob/fix/exchange-slh-reserve-accounting/tests/test_webapp_exchange_cancel.py

## Resume prompt for desktop ChatGPT
Continue the SLH exchange reserve-accounting audit from `osifeu-prog/slh-bot`, branch `fix/exchange-slh-reserve-accounting`. First read `docs/SLH_EXCHANGE_RESERVE_AUDIT_HANDOFF_2026-10-09.md`, then inspect all call sites/readers of `live_token_balance`, `exchange_reserved_slh`, `reserve_in_db`, `settle_reserve_in_db`, and `release_reserve_in_db`. Do not assume CI success covers this bug. Do not merge, deploy, change gates, or perform live financial operations. Establish consistent semantics, add isolated tests that fail on current behavior, then run focused and full regression tests and report exact evidence.
