"""Server-side trading certification and first-15 referral course campaign."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import state_manager

TRADER_COURSE_ID = "algo_trading_999"
TRADER_CERTIFICATION_STAGE = 7
TRADER_QUIZ_VERSION = "slh-trader-readiness-v1"
TRADER_PASS_SCORE = 8
REFERRAL_PROMO_LIMIT = 15
REFERRAL_PROMO_KEY = "slh_trader_course_referral_promo"

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def has_trader_certification(uid: str, db: dict[str, Any] | None = None) -> bool:
    """Require both the server-side pass record and completed course progression."""
    uid = str(uid or "").strip()
    if not uid:
        return False
    if db is None:
        try:
            db = state_manager.load_db()
        except Exception:
            return False
    users = db.get("users", {})
    user = users.get(uid) if isinstance(users, dict) else None
    certifications = db.get("trader_certifications", {})
    record = certifications.get(uid) if isinstance(certifications, dict) else None
    if not isinstance(user, dict) or not isinstance(record, dict):
        return False
    academy = user.get("academy", {})
    courses = academy.get("courses", {}) if isinstance(academy, dict) else {}
    course = courses.get(TRADER_COURSE_ID, {}) if isinstance(courses, dict) else {}
    completed = course.get("completed", []) if isinstance(course, dict) else []
    try:
        completed_ids = {int(x) for x in completed}
        score = int(record.get("score", 0))
    except (TypeError, ValueError):
        return False
    return (
        record.get("passed") is True
        and record.get("critical_pass") is True
        and record.get("quiz_version") == TRADER_QUIZ_VERSION
        and score >= TRADER_PASS_SCORE
        and set(range(1, TRADER_CERTIFICATION_STAGE + 1)).issubset(completed_ids)
    )

def award_referral_course(referrer_uid: str, referred_uid: str, *, now: str | None = None) -> dict[str, Any]:
    """Award a free course to the first 15 distinct referrers atomically.

    Proof is a unique referred_by relationship after successful onboarding.
    Merely opening or sharing a link is not verifiable and does not qualify.
    """
    referrer_uid = str(referrer_uid or "").strip()
    referred_uid = str(referred_uid or "").strip()
    if not referrer_uid.isdigit() or not referred_uid.isdigit() or referrer_uid == referred_uid:
        return {"status": "INELIGIBLE", "reason": "INVALID_REFERRAL"}
    timestamp = str(now or _now())

    def mutate(db: dict[str, Any]) -> dict[str, Any]:
        users = db.get("users", {})
        referrer = users.get(referrer_uid) if isinstance(users, dict) else None
        referred = users.get(referred_uid) if isinstance(users, dict) else None
        if not isinstance(referrer, dict) or not isinstance(referred, dict):
            return {"status": "INELIGIBLE", "reason": "USER_NOT_FOUND"}
        if str((referred.get("referral") or {}).get("referred_by") or "") != referrer_uid:
            return {"status": "INELIGIBLE", "reason": "SUCCESSFUL_REFERRAL_NOT_PROVEN"}

        campaign = db.setdefault(REFERRAL_PROMO_KEY, {"awards": {}})
        if not isinstance(campaign, dict):
            raise ValueError("TRADER_REFERRAL_PROMO_STATE_INVALID")
        awards = campaign.setdefault("awards", {})
        if not isinstance(awards, dict):
            raise ValueError("TRADER_REFERRAL_PROMO_AWARDS_INVALID")
        if referrer_uid in awards:
            return {"status": "ALREADY_AWARDED", "award": dict(awards[referrer_uid])}

        academy = referrer.setdefault("academy", {})
        courses = academy.setdefault("courses", {})
        if not isinstance(courses, dict):
            raise ValueError("ACADEMY_COURSES_INVALID")
        if TRADER_COURSE_ID in courses:
            return {"status": "ALREADY_HAS_COURSE", "remaining": max(0, REFERRAL_PROMO_LIMIT - len(awards))}
        if len(awards) >= REFERRAL_PROMO_LIMIT:
            return {"status": "PROMO_FULL", "remaining": 0}

        slot = len(awards) + 1
        courses[TRADER_COURSE_ID] = {
            "stage": 0,
            "completed": [],
            "access_grant": "verified_referral_first15",
            "granted_at": timestamp,
        }
        award = {
            "uid": referrer_uid,
            "referred_uid": referred_uid,
            "slot": slot,
            "granted_at": timestamp,
            "course_id": TRADER_COURSE_ID,
            "source": "verified_successful_referral",
        }
        awards[referrer_uid] = award
        campaign["limit"] = REFERRAL_PROMO_LIMIT
        campaign["updated_at"] = timestamp
        return {"status": "GRANTED", "award": dict(award), "remaining": max(0, REFERRAL_PROMO_LIMIT - len(awards))}

    return state_manager.atomic_update(mutate)

def referral_course_promo_status(uid: str, db: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return safe per-user status and aggregate campaign count."""
    uid = str(uid or "").strip()
    if db is None:
        db = state_manager.load_db()
    campaign = db.get(REFERRAL_PROMO_KEY, {})
    awards = campaign.get("awards", {}) if isinstance(campaign, dict) else {}
    if not isinstance(awards, dict):
        awards = {}
    award = awards.get(uid)
    return {
        "limit": REFERRAL_PROMO_LIMIT,
        "awarded_count": len(awards),
        "remaining": max(0, REFERRAL_PROMO_LIMIT - len(awards)),
        "awarded": isinstance(award, dict),
        "slot": award.get("slot") if isinstance(award, dict) else None,
        "qualification": "one unique referred participant must complete registration",
    }
