"""Expired one-day Holiday referral campaign.

The original 100,000 SLH grant was a one-day campaign for 2026-09-11.
This module remains for historical auditability, but it must not create
new entries or settle grants after the campaign date.
"""
 
from datetime import date, datetime, time
from zoneinfo import ZoneInfo
 
import state_manager
from core.identity import OWNER_TELEGRAM_ID
 
CAMPAIGN_ID = "holiday_referral_20260911"
CAMPAIGN_TZ = ZoneInfo("Asia/Jerusalem")
CAMPAIGN_DATE = date(2026, 9, 11)
GRANT_AMOUNT = 100_000
DISTRIBUTOR_UID = str(OWNER_TELEGRAM_ID)
 
 
def _now():
    return datetime.now(CAMPAIGN_TZ)
 
 
def is_active(now=None):
    now = now or _now()
    return now.astimezone(CAMPAIGN_TZ).date() == CAMPAIGN_DATE
 
 
def record_entry(uid, *, source="public_bot_link_inferred", now=None):
    """Record campaign entry evidence only on the original campaign date."""
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
    """Return a read-only eligibility decision for the expired campaign."""
    uid = str(uid)
    now = now or _now()
    db = state_manager.load_db()
    user = db.get("users", {}).get(uid)
    if not user:
        return {"eligible": False, "reason": "USER_NOT_FOUND"}
    if not is_active(now):
        return {
            "eligible": False,
            "reason": "CAMPAIGN_EXPIRED",
            "campaign_id": CAMPAIGN_ID,
            "amount": GRANT_AMOUNT,
        }
 
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
    """Attempt settlement only while the original campaign is active."""
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
