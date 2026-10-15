"""Retryable settlement for persisted referral relationships.

Referral attribution and reward delivery are separate operations. If attribution is
saved but reward settlement fails, later /join attempts can safely retry the
canonical relationship; the reward service's idempotency keys prevent duplicates.
"""
from __future__ import annotations

import state_manager


def settle_persisted_referral(referred_uid: str) -> dict:
    """Retry rewards for the referred user's already-persisted relationship.

    The relationship and referrer are read from canonical state. Pending attribution
    is cleared only after reward settlement succeeds and the relationship is still
    unchanged in the atomic mutation.
    """
    uid = str(referred_uid or "").strip()
    if not uid:
        return {"status": "IGNORED", "reason": "INVALID_REFERRED_UID"}

    db = state_manager.load_db()
    users = db.get("users")
    user = users.get(uid) if isinstance(users, dict) else None
    if not isinstance(user, dict):
        return {"status": "NO_USER", "rewards": None}

    referral = user.get("referral")
    referrer_uid = str(
        referral.get("referred_by") or ""
    ).strip() if isinstance(referral, dict) else ""
    if not referrer_uid or referrer_uid == uid:
        return {"status": "NO_REFERRAL", "rewards": None}

    referrer = users.get(referrer_uid)
    if not isinstance(referrer, dict):
        return {"status": "REFERRER_NOT_FOUND", "rewards": None}

    from core.referral_reward import settle_successful_referral

    # May raise on a partial failure. Do not clear pending attribution in that case.
    # Each component reward has a stable referred-user idempotency key.
    rewards = settle_successful_referral(referrer_uid, uid)

    def finalize(current_db):
        current_users = current_db.get("users")
        current_user = (
            current_users.get(uid) if isinstance(current_users, dict) else None
        )
        current_referral = (
            current_user.get("referral")
            if isinstance(current_user, dict) else None
        )
        if not isinstance(current_referral, dict):
            return False
        if str(current_referral.get("referred_by") or "").strip() != referrer_uid:
            return False

        pending = current_db.get("pending_referrals")
        if isinstance(pending, dict) and str(pending.get(uid) or "").strip() == referrer_uid:
            pending.pop(uid, None)
        return True

    if not state_manager.atomic_update(finalize):
        raise RuntimeError("REFERRAL_RELATION_CHANGED_DURING_SETTLEMENT")

    return {
        "status": "SETTLED",
        "referrer_uid": referrer_uid,
        "referred_uid": uid,
        "rewards": rewards,
    }
