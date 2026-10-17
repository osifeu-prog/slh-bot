"""Idempotent daily engagement reward, settled as non-monetary Points.

This feature intentionally does not mint Credits or SLH. Points use the existing
per-user points ledger and leaderboard balance, with an Asia/Jerusalem calendar
day to match the product's user-facing timezone.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import state_manager
from core.profile_manager import add_points_in_db
from core.tokenomics import REWARDS


DAILY_TZ = ZoneInfo("Asia/Jerusalem")
DAILY_POINTS = int(REWARDS["daily_points"])


def _local_now(now=None):
    if now is None:
        return datetime.now(DAILY_TZ)
    if not isinstance(now, datetime):
        raise TypeError("now must be a datetime")
    if now.tzinfo is None or now.utcoffset() is None:
        return now.replace(tzinfo=DAILY_TZ)
    return now.astimezone(DAILY_TZ)


def _points_total(user):
    try:
        return int((user.get("gamification") or {}).get("points", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _daily_state(user):
    value = user.get("daily_rewards")
    if value is None:
        value = {}
        user["daily_rewards"] = value
    elif not isinstance(value, dict):
        raise ValueError("DAILY_REWARD_STATE_INVALID")
    return value


def _has_points_event(user, idempotency_key):
    ledger = user.get("points_ledger")
    if not isinstance(ledger, list):
        return False
    return any(
        isinstance(item, dict)
        and isinstance(item.get("meta"), dict)
        and item["meta"].get("idempotency_key") == idempotency_key
        for item in ledger
    )


def get_daily_status(uid, *, now=None):
    """Read today's eligibility without creating a user or mutating the DB."""
    uid = str(uid).strip()
    if not uid:
        raise ValueError("uid is required")
    local_now = _local_now(now)
    today = local_now.date()
    db = state_manager.load_db()
    user = (db.get("users") or {}).get(uid)
    if not isinstance(user, dict):
        return {
            "status": "user_not_found",
            "date": today.isoformat(),
            "daily_points": DAILY_POINTS,
            "claimed_today": False,
            "streak": 0,
            "next_streak": 1,
        }

    raw = user.get("daily_rewards")
    daily = raw if isinstance(raw, dict) else {}
    last_date = str(daily.get("last_claim_date") or "")
    try:
        last_day = date.fromisoformat(last_date)
    except ValueError:
        last_day = None
    stored_streak = max(0, int(daily.get("streak", 0) or 0))
    next_streak = stored_streak + 1 if last_day == today - timedelta(days=1) else 1
    claimed = last_date == today.isoformat()

    return {
        "status": "already_claimed" if claimed else "claim_available",
        "date": today.isoformat(),
        "daily_points": DAILY_POINTS,
        "claimed_today": claimed,
        "streak": stored_streak,
        "next_streak": stored_streak if claimed else next_streak,
        "last_claim_date": last_date or None,
        "total_claims": max(0, int(daily.get("total_claims", 0) or 0)),
        "points_total": _points_total(user),
    }


def claim_daily_reward(uid, *, now=None):
    """Grant the daily Points reward at most once for the user's local date."""
    uid = str(uid).strip()
    if not uid:
        raise ValueError("uid is required")
    local_now = _local_now(now)
    claim_day = local_now.date()
    claim_date = claim_day.isoformat()
    idempotency_key = f"daily-points:{uid}:{claim_date}"

    def mutate(db):
        users = db.get("users")
        user = users.get(uid) if isinstance(users, dict) else None
        if not isinstance(user, dict):
            return {
                "status": "user_not_found",
                "date": claim_date,
                "daily_points": DAILY_POINTS,
                "points_awarded": 0,
                "streak": 0,
            }

        daily = _daily_state(user)
        last_date = str(daily.get("last_claim_date") or "")
        if last_date == claim_date:
            return {
                "status": "already_claimed",
                "date": claim_date,
                "daily_points": DAILY_POINTS,
                "points_awarded": 0,
                "streak": max(0, int(daily.get("streak", 0) or 0)),
                "total_claims": max(0, int(daily.get("total_claims", 0) or 0)),
                "points_total": _points_total(user),
            }

        try:
            last_day = date.fromisoformat(last_date)
        except ValueError:
            last_day = None
        previous_streak = max(0, int(daily.get("streak", 0) or 0))
        streak = previous_streak + 1 if last_day == claim_day - timedelta(days=1) else 1
        total_claims = max(0, int(daily.get("total_claims", 0) or 0))

        # Repair a partially populated daily summary without awarding twice if
        # the canonical user Points ledger already has this day's idempotency key.
        already_in_ledger = _has_points_event(user, idempotency_key)
        if not already_in_ledger:
            add_points_in_db(
                db,
                uid,
                DAILY_POINTS,
                reason="daily:claim",
                meta={
                    "idempotency_key": idempotency_key,
                    "claim_date": claim_date,
                    "timezone": "Asia/Jerusalem",
                    "streak": streak,
                },
            )
        total_claims += 1
        daily.update({
            "last_claim_date": claim_date,
            "streak": streak,
            "total_claims": total_claims,
            "last_idempotency_key": idempotency_key,
        })
        return {
            "status": "already_claimed" if already_in_ledger else "claimed",
            "date": claim_date,
            "daily_points": DAILY_POINTS,
            "points_awarded": 0 if already_in_ledger else DAILY_POINTS,
            "streak": streak,
            "total_claims": total_claims,
            "points_total": _points_total(user),
        }

    return state_manager.atomic_update(mutate)
