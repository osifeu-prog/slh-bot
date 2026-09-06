# Store purchase saga verification

This change set introduces purchase state, request-idempotent `/buy`, pre-charge hardware inventory reservation, purchase-bound hardware identity, and reusable license issuance.

Verification performed by source review:

- Existing `main` behavior was inspected before patching.
- Economy mutations remain delegated to `economy_service.record_transaction()` through the economy bridge.
- Purchase state is stored in the existing `state/db.json`.
- Telegram `/buy` derives a stable request identity from chat/message identity.
- Hardware inventory is reserved before the debit.
- Fulfillment retries reuse the purchase identity.
- Existing licenses are reused for the same device/owner.
- `main` and Railway production were not changed or deployed.

Runtime execution of the new tests is not available from the current connector environment because the repository cannot be cloned from the network and the repository has no discovered GitHub Actions workflow.
