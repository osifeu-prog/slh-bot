"""First-touch, idempotent referral-start attribution.

This module records telemetry only. Referral rewards are still granted exclusively by
the existing successful-join path in handlers.join_handler.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import state_manager


def _uid(value: Any) -> str | None:
    value = str(value or "").strip()
    return value if value.isdigit() else None


def _timestamp(value: str | None = None) -> str:
    return str(value) if value else datetime.now(timezone.utc).isoformat()


def record_referral_start(
    referred_uid: str,
    referrer_uid: str,
    *,
    is_new_user: bool,
    now: str | None = None,
) -> dict[str, Any]:
    """Record at most one referral start per referred UID, preserving first touch.

    A new user receives a pending-referral attribution but no reward. An existing
    account start is counted separately and never rewrites prior attribution.
    """
    uid = _uid(referred_uid)
    requested_referrer = _uid(referrer_uid)
    if not uid or not requested_referrer or uid == requested_referrer:
        return {
            "recorded": False,
            "already_recorded": False,
            "status": "IGNORED",
            "reason": "INVALID_REFERRAL",
        }

    timestamp = _timestamp(now)

    def mutate(db: dict[str, Any]) -> dict[str, Any]:
        users = db.get("users")
        if not isinstance(users, dict) or requested_referrer not in users:
            return {
                "recorded": False,
                "already_recorded": False,
                "status": "IGNORED",
                "reason": "REFERRER_NOT_FOUND",
            }

        events = db.setdefault("referral_start_events", {})
        if not isinstance(events, dict):
            raise ValueError("REFERRAL_START_EVENTS_INVALID")

        existing = events.get(uid)
        if isinstance(existing, dict):
            return {
                **existing,
                "recorded": False,
                "already_recorded": True,
            }

        pending = db.setdefault("pending_referrals", {})
        if not isinstance(pending, dict):
            raise ValueError("PENDING_REFERRALS_INVALID")

        prior_pending = pending.get(uid)
        if prior_pending:
            actual_referrer = _uid(prior_pending)
            if (
                not actual_referrer
                or actual_referrer == uid
                or actual_referrer not in users
            ):
                return {
                    "recorded": False,
                    "already_recorded": False,
                    "status": "IGNORED",
                    "reason": "PENDING_REFERRER_INVALID",
                }
        else:
            actual_referrer = requested_referrer

        current_user = users.get(uid)
        has_pending_join = bool(
            is_new_user
            or prior_pending
            or (
                isinstance(current_user, dict)
                and current_user.get("joined") is not True
                and actual_referrer == requested_referrer
            )
        )
        if has_pending_join and not prior_pending:
            pending[uid] = actual_referrer

        status = "PENDING_JOIN" if has_pending_join else "EXISTING_USER"
        event = {
            "referred_uid": uid,
            "referrer_uid": actual_referrer,
            "first_seen_at": timestamp,
            "status": status,
            "source": "telegram_start_payload",
            "is_new_user_at_start": bool(is_new_user),
        }
        events[uid] = event
        return {
            **event,
            "recorded": True,
            "already_recorded": False,
        }

    return state_manager.atomic_update(mutate)


def mark_join_completed(
    referred_uid: str,
    *,
    now: str | None = None,
) -> dict[str, Any]:
    """Mark onboarding complete with a stable timestamp and convert pending attribution.

    This changes no referral count, balance, reward or points. Those remain in the
    canonical successful-referral reward path.
    """
    uid = _uid(referred_uid)
    if not uid:
        return {"status": "IGNORED", "reason": "UID_INVALID"}

    def mutate(db: dict[str, Any]) -> dict[str, Any]:
        users = db.get("users")
        user = users.get(uid) if isinstance(users, dict) else None
        if not isinstance(user, dict):
            return {"status": "NO_USER", "joined_at": None}

        joined_at = str(user.get("joined_at") or _timestamp(now))
        user.setdefault("joined_at", joined_at)
        events = db.get("referral_start_events")
        event = events.get(uid) if isinstance(events, dict) else None
        status = "NO_REFERRAL"
        if isinstance(event, dict):
            if event.get("status") == "PENDING_JOIN":
                event["status"] = "CONVERTED"
                event["converted_at"] = joined_at
            status = str(event.get("status") or "UNKNOWN")

        return {"status": status, "joined_at": joined_at}

    return state_manager.atomic_update(mutate)


def referral_start_stats(
    referrer_uid: str,
    *,
    db: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Return aggregate-only unique start and conversion counts for a referrer."""
    uid = str(referrer_uid or "").strip()
    if db is None:
        db = state_manager.load_db()
    events = db.get("referral_start_events")
    if not isinstance(events, dict):
        events = {}

    mine = [
        event
        for event in events.values()
        if isinstance(event, dict)
        and str(event.get("referrer_uid") or "") == uid
    ]
    statuses = [str(event.get("status") or "") for event in mine]
    return {
        "unique_starts": len(mine),
        "pending_joins": statuses.count("PENDING_JOIN"),
        "converted_joins": statuses.count("CONVERTED"),
        "existing_user_starts": statuses.count("EXISTING_USER"),
    }
