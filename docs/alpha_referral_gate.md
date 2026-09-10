# Alpha referral reward gate

Referral rewards must be issued only after `_persist_referral(uid, ref_uid)` returns truthy. The persisted relationship is the authority boundary; a pending referral or a valid-looking referrer is evidence, not successful persistence.

The reward remains idempotent via `ref:{uid}`. Pending referral state is cleared after the referral path is evaluated.

This document is an implementation note for the Alpha referral integrity gate; it does not define SLH AIR allocation policy.
