"""Referral rewards for successful user acquisition.

Permanent referral reward:
- 0.9 internal Credits per successful referral.
- 10 Points per successful referral.
Launch offer:
- 5 successful referrals unlock one VIP month.
"""
 
import time
 
import state_manager
from core.reward_engine import grant
from core.stars_price_authority import VIP_SUBSCRIPTION_PERIOD
 
REFERRALS_REQUIRED = 5
SUCCESS_REFERRAL_CREDITS = 0.9
SUCCESS_REFERRAL_POINTS = 10
MAX_AWARDS = 10
OFFER_ENDS_AT = 1793483999
AWARDS_KEY = "referral_vip_awards"
 
 
def offer_open(now=None):
    return int(time.time() if now is None else now) < OFFER_ENDS_AT
 
 
def progress(uid):
    db = state_manager.load_db()
    user = db.get("users", {}).get(str(uid), {})
    count = int((user.get("referral") or {}).get("count", 0) or 0)
    awards = db.get(AWARDS_KEY) or {}
    return {
        "count": count,
        "required": REFERRALS_REQUIRED,
        "remaining": max(0, REFERRALS_REQUIRED - count),
        "awarded": str(uid) in awards,
        "awards_left": max(0, MAX_AWARDS - len(awards)),
        "offer_open": offer_open(),
        "per_successful_referral": {
            "credits": SUCCESS_REFERRAL_CREDITS,
            "points": SUCCESS_REFERRAL_POINTS,
        },
    }
 
 
def settle_successful_referral(referrer_uid, referred_uid):
    """Apply the permanent referral rewards exactly once per successful join."""
    referrer_uid = str(referrer_uid)
    referred_uid = str(referred_uid)
 
    if not referrer_uid or not referred_uid or referrer_uid == referred_uid:
        raise ValueError("INVALID_REFERRAL")
 
    points_result = grant(
        referrer_uid,
        "referral",
        points=SUCCESS_REFERRAL_POINTS,
        idempotency_key=f"ref:{referred_uid}",
    )
    credits_result = grant(
        referrer_uid,
        "referral_success_bonus",
        credits=SUCCESS_REFERRAL_CREDITS,
        idempotency_key=f"referral-credit:{referred_uid}",
    )
    vip_award = maybe_award(referrer_uid)
 
    return {
        "referrer_uid": referrer_uid,
        "referred_uid": referred_uid,
        "points": points_result,
        "credits": credits_result,
        "vip": vip_award,
    }
 
 
def maybe_award(uid, now=None):
    uid = str(uid)
    now = int(time.time() if now is None else now)
    if not offer_open(now):
        return None
 
    def mutate(db):
        awards = db.setdefault(AWARDS_KEY, {})
        if uid in awards or len(awards) >= MAX_AWARDS:
            return None
        user = db.setdefault("users", {}).get(uid)
        if not user:
            return None
        count = int((user.get("referral") or {}).get("count", 0) or 0)
        if count < REFERRALS_REQUIRED:
            return None
        previous = int(user.get("vip_access_until", 0) or 0)
        until = max(now, previous) + VIP_SUBSCRIPTION_PERIOD
        perms = user.setdefault("permissions", [])
        if "vip_access" not in perms:
            perms.append("vip_access")
        user["vip_access_until"] = until
        record = {
            "uid": uid,
            "referrals": count,
            "granted_at": now,
            "expires_at": until,
            "source": "referral_milestone",
        }
        awards[uid] = record
        return dict(record)
 
    return state_manager.atomic_update(mutate)
