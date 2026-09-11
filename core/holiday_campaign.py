"""Holiday Alpha campaign attribution, eligibility, and settlement.

Campaign entry/finalization remain evidence-only. Once a user is eligible,
settlement transfers existing SLH through the canonical distribution authority.
No tokens are minted here.
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import state_manager
from core.identity import OWNER_TELEGRAM_ID

CAMPAIGN_ID = "holiday_referral_20260911"
CAMPAIGN_TZ = ZoneInfo("Asia/Jerusalem")
GRANT_AMOUNT = 100_000
DISTRIBUTOR_UID = str(OWNER_TELEGRAM_ID)


def _now():
    return datetime.now(CAMPAIGN_TZ)


def is_active(now=None):
    now = now or _now()
    start = datetime.combine(now.date(), time.min, tzinfo=CAMPAIGN_TZ)
    end = datetime.combine(now.date(), time.max, tzinfo=CAMPAIGN_TZ)
    return start <= now <= end


def record_entry(uid, *, source="public_bot_link_inferred", now=None):
    """Record first campaign-day entry evidence without creating a user."""
    uid = str(uid)
    now = now or _now()
    if not is_active(now):
        return False

    def mutate(db):
        pending = db.setdefault("pending_campaign_entries", {})
        if uid not in pending:
            pending[uid] = {
                "campaign_id": CAMPAIGN_ID,
                "entered_at": now.isoformat(),
                "source": source,
                "attribution_confidence": "inferred",
            }
        return dict(pending[uid])

    return state_manager.atomic_update(mutate)


def finalize_entry(uid, now=None):
    """Move pending campaign evidence onto a successfully onboarded user."""
    uid = str(uid)
    now = now or _now()

    def mutate(db):
        pending = db.setdefault("pending_campaign_entries", {})
        evidence = pending.get(uid)
        if not evidence:
            return False
        user = db.setdefault("users", {}).get(uid)
        if not user:
            return False
        campaigns = user.setdefault("campaigns", {})
        campaigns.setdefault(CAMPAIGN_ID, dict(evidence))
        pending.pop(uid, None)
        return True

    return state_manager.atomic_update(mutate)


def eligibility(uid, now=None):
    """Return a read-only eligibility decision for the 100K SLH campaign."""
    uid = str(uid)
    db = state_manager.load_db()
    user = db.get("users", {}).get(uid)
    if not user:
        return {"eligible": False, "reason": "USER_NOT_FOUND"}

    campaign = (user.get("campaigns") or {}).get(CAMPAIGN_ID)
    if not campaign:
        return {"eligible": False, "reason": "NO_CAMPAIGN_ENTRY"}
    if not user.get("joined"):
        return {"eligible": False, "reason": "NOT_JOINED"}

    referral_count = int((user.get("referral") or {}).get("count", 0) or 0)
    if referral_count < 1:
        return {"eligible": False, "reason": "NO_SUCCESSFUL_REFERRAL"}

    return {
        "eligible": True,
        "campaign_id": CAMPAIGN_ID,
        "amount": GRANT_AMOUNT,
        "attribution_confidence": campaign.get("attribution_confidence", "inferred"),
        "entered_at": campaign.get("entered_at"),
        "successful_referrals": referral_count,
    }


def settle(uid, now=None):
    """Settle one eligible user exactly once through canonical SLH authority."""
    uid = str(uid)
    decision = eligibility(uid, now=now)
    if not decision.get("eligible"):
        return decision

    from core.slh_distribution import distribute

    event_id = f"{CAMPAIGN_ID}:{uid}"
    result = distribute(
        distributor_uid=DISTRIBUTOR_UID,
        recipient_uid=uid,
        amount=GRANT_AMOUNT,
        reason="holiday_referral_grant",
        event_id=event_id,
    )
    return {**decision, "settlement": result}


def report(now=None):
    """Produce a read-only campaign eligibility report from current DB state."""
    db = state_manager.load_db()
    users = db.get("users", {})
    rows = []
    for uid, user in users.items():
        decision = eligibility(uid, now=now)
        if (user.get("campaigns") or {}).get(CAMPAIGN_ID):
            rows.append({"uid": str(uid), **decision})
    return rows
