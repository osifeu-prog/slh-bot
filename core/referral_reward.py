"""Referral reward: 5 referrals grant one VIP month."""

import time

import state_manager
from core.stars_price_authority import VIP_SUBSCRIPTION_PERIOD

REFERRALS_REQUIRED = 5
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
