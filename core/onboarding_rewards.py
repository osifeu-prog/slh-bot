"""Idempotent Credits gift for fully completed new-user onboarding.

Eligibility is recorded only after the canonical join flow has saved the profile
and started the Academy. This service uses the Economy Authority, never edits
balances directly, and leaves a pending marker to support safe /start retries.
"""
from datetime import datetime, timezone

import state_manager
from core.economy_service import record_transaction

SIGNUP_BONUS_CREDITS = 5
SIGNUP_BONUS_REASON = "onboarding:signup_bonus"


def _key(uid: str) -> str:
    return f"onboarding-signup-credits:v1:{uid}"


def _user_ready(db: dict, uid: str) -> bool:
    user = (db.get("users") or {}).get(str(uid))
    academy = user.get("academy") if isinstance(user, dict) else None
    courses = academy.get("courses") if isinstance(academy, dict) else None
    return bool(
        isinstance(user, dict)
        and user.get("joined") is True
        and isinstance(courses, dict)
        and isinstance(courses.get("bitcoin_mastery"), dict)
    )


def mark_signup_bonus_pending(uid: str) -> dict:
    """Create the reward eligibility marker after successful join + Academy setup."""
    uid = str(uid or "").strip()
    if not uid.isdigit():
        return {"status": "BLOCKED", "reason": "INVALID_UID"}

    def mutate(db):
        if not _user_ready(db, uid):
            return {"status": "BLOCKED", "reason": "ONBOARDING_NOT_COMPLETE"}
        user = db["users"][uid]
        status = str(user.get("onboarding_signup_bonus_status") or "").upper()
        if status in {"PENDING", "AWARDED"}:
            return {"status": status}
        user["onboarding_signup_bonus_status"] = "PENDING"
        user["onboarding_signup_bonus_eligible_at"] = datetime.now(timezone.utc).isoformat()
        return {"status": "PENDING"}

    return state_manager.atomic_update(mutate)


def grant_signup_bonus(uid: str) -> dict:
    """Grant exactly once only to a newly-qualified user with a pending marker."""
    uid = str(uid or "").strip()
    if not uid.isdigit():
        return {"status": "BLOCKED", "reason": "INVALID_UID"}

    db = state_manager.load_db()
    user = (db.get("users") or {}).get(uid)
    if not isinstance(user, dict) or not _user_ready(db, uid):
        return {"status": "BLOCKED", "reason": "ONBOARDING_NOT_COMPLETE"}

    status = str(user.get("onboarding_signup_bonus_status") or "").upper()
    key = _key(uid)
    rows = db.get("ledger", [])
    matched = [
        row for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("meta"), dict)
        and row["meta"].get("idempotency_key") == key
    ] if isinstance(rows, list) else []

    if status == "AWARDED":
        if len(matched) == 1:
            row = matched[0]
            if (
                str(row.get("uid")) == uid
                and row.get("reason") == SIGNUP_BONUS_REASON
                and float(row.get("amount", 0) or 0) == SIGNUP_BONUS_CREDITS
            ):
                return {"status": "ALREADY_AWARDED", "balance_after": row.get("after")}
        return {"status": "BLOCKED", "reason": "AWARD_MARKER_LEDGER_MISMATCH"}

    if status != "PENDING":
        return {"status": "NOT_PENDING"}

    result = record_transaction(
        uid,
        SIGNUP_BONUS_CREDITS,
        SIGNUP_BONUS_REASON,
        {
            "source": "completed_join_onboarding",
            "eligibility": "joined_profile_and_academy_initialized",
            "idempotency_key": key,
        },
        return_details=True,
    )
    tx_status = str(result.get("status") or "UNKNOWN")
    if tx_status not in {"APPLIED", "DUPLICATE"}:
        return {"status": "BLOCKED", "reason": f"TRANSACTION_{tx_status}"}

    def finalize(db2):
        current = (db2.get("users") or {}).get(uid)
        if not isinstance(current, dict) or not _user_ready(db2, uid):
            return {"status": "BLOCKED", "reason": "ONBOARDING_CHANGED"}
        all_rows = db2.get("ledger", [])
        final_rows = [
            row for row in all_rows
            if isinstance(row, dict)
            and isinstance(row.get("meta"), dict)
            and row["meta"].get("idempotency_key") == key
        ] if isinstance(all_rows, list) else []
        if len(final_rows) != 1:
            return {"status": "BLOCKED", "reason": "LEDGER_KEY_NOT_UNIQUE"}
        row = final_rows[0]
        if (
            str(row.get("uid")) != uid
            or row.get("reason") != SIGNUP_BONUS_REASON
            or float(row.get("amount", 0) or 0) != SIGNUP_BONUS_CREDITS
        ):
            return {"status": "BLOCKED", "reason": "LEDGER_KEY_CONFLICT"}
        current["onboarding_signup_bonus_status"] = "AWARDED"
        current["onboarding_signup_bonus_awarded_at"] = str(
            current.get("onboarding_signup_bonus_awarded_at")
            or datetime.now(timezone.utc).isoformat()
        )
        return {"status": "GRANTED" if tx_status == "APPLIED" else "DUPLICATE",
                "balance_after": row.get("after"),
                "credits_awarded": SIGNUP_BONUS_CREDITS}

    return state_manager.atomic_update(finalize)
