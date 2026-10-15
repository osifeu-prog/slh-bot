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
 
 

def settle_persisted_referral(referred_uid):
    """Recover referral rewards after a persisted join, safely across retries."""
    referred_uid = str(referred_uid).strip()
    if not referred_uid:
        return {"status": "NO_PERSISTED_REFERRAL"}

    db = state_manager.load_db()
    user = (db.get("users") or {}).get(referred_uid) or {}
    referral = user.get("referral") or {}
    referrer_uid = str(referral.get("referred_by") or "").strip()
    if not referrer_uid or referrer_uid == referred_uid:
        return {"status": "NO_PERSISTED_REFERRAL"}

    settlements = db.get("referral_reward_settlements") or {}
    existing = settlements.get(referred_uid) if isinstance(settlements, dict) else None
    if (isinstance(existing, dict) and existing.get("status") == "settled"
            and str(existing.get("referrer_uid")) == referrer_uid):
        return {"status": "ALREADY_SETTLED", "referrer_uid": referrer_uid}

    rewards = settle_successful_referral(referrer_uid, referred_uid)
    settled_at = int(time.time())

    def mark_settled(current_db):
        current_user = (current_db.get("users") or {}).get(referred_uid) or {}
        current_referral = current_user.get("referral") or {}
        if str(current_referral.get("referred_by") or "") != referrer_uid:
            raise ValueError("REFERRAL_RELATION_CHANGED_DURING_SETTLEMENT")
        records = current_db.setdefault("referral_reward_settlements", {})
        if not isinstance(records, dict):
            raise ValueError("REFERRAL_SETTLEMENT_STATE_INVALID")
        records[referred_uid] = {
            "referred_uid": referred_uid,
            "referrer_uid": referrer_uid,
            "status": "settled",
            "settled_at": settled_at,
            "policy": "10_points_0.9_credits_idempotent",
        }
        return dict(records[referred_uid])

    marker = state_manager.atomic_update(mark_settled)
    return {
        "status": "SETTLED",
        "referrer_uid": referrer_uid,
        "rewards": rewards,
        "settlement": marker,
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
