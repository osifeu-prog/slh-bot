"""Referral rewards for successful user acquisition.

Permanent referral reward:
- 0.9 internal Credits per successful referral.
- 10 Points per successful referral.
Launch offer:
- 5 successful referrals unlock one VIP month.

The referral relationship and referral count are persisted before rewards. If
settlement fails midway, recover_persisted_referral() safely replays the same
idempotency keys and marks completion only after both authoritative ledgers
prove the expected reward rows exist.
"""

import math
import time
from datetime import datetime, timezone

import state_manager
from core.reward_engine import grant
from core.stars_price_authority import VIP_SUBSCRIPTION_PERIOD

REFERRALS_REQUIRED = 5
SUCCESS_REFERRAL_CREDITS = 0.9
SUCCESS_REFERRAL_POINTS = 10
MAX_AWARDS = 10
OFFER_ENDS_AT = 1793483999
AWARDS_KEY = "referral_vip_awards"
SETTLEMENTS_KEY = "referral_reward_settlements"


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
    """Apply the permanent referral rewards with stable per-referral keys."""
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


def _reward_ledger_matches(db, referrer_uid, referred_uid, *, require_complete=False):
    """Validate reward idempotency records before and after replay.

    The Credits ledger is authoritative for Credits; the user's points ledger
    is authoritative for Points. The optional JSON rewards ledger is not used
    as proof of a balance mutation.
    """
    users = db.get("users")
    if not isinstance(users, dict):
        raise ValueError("REFERRAL_USERS_UNREADABLE")

    points_key = f"ref:{referred_uid}"
    credits_key = f"referral-credit:{referred_uid}"
    points_matches = []
    for ledger_uid, user in users.items():
        if not isinstance(user, dict):
            continue
        points_ledger = user.get("points_ledger")
        if not isinstance(points_ledger, list):
            continue
        for row in points_ledger:
            if not isinstance(row, dict):
                continue
            meta = row.get("meta")
            if isinstance(meta, dict) and meta.get("idempotency_key") == points_key:
                points_matches.append((str(ledger_uid), row))

    if len(points_matches) > 1:
        raise ValueError("REFERRAL_POINTS_IDEMPOTENCY_CONFLICT")
    if points_matches:
        ledger_uid, row = points_matches[0]
        try:
            amount = float(row.get("amount"))
        except (TypeError, ValueError, OverflowError):
            amount = math.nan
        if (
            ledger_uid != referrer_uid
            or str(row.get("reason") or "") != "referral"
            or not math.isfinite(amount)
            or not math.isclose(amount, SUCCESS_REFERRAL_POINTS, rel_tol=0.0, abs_tol=1e-9)
        ):
            raise ValueError("REFERRAL_POINTS_IDEMPOTENCY_CONFLICT")

    credit_ledger = db.get("ledger")
    if not isinstance(credit_ledger, list):
        raise ValueError("REFERRAL_CREDITS_LEDGER_UNREADABLE")
    credits_matches = []
    for row in credit_ledger:
        if not isinstance(row, dict):
            continue
        meta = row.get("meta")
        if isinstance(meta, dict) and meta.get("idempotency_key") == credits_key:
            credits_matches.append(row)

    if len(credits_matches) > 1:
        raise ValueError("REFERRAL_CREDITS_IDEMPOTENCY_CONFLICT")
    if credits_matches:
        row = credits_matches[0]
        try:
            amount = float(row.get("amount"))
            before = float(row.get("before"))
            after = float(row.get("after"))
        except (TypeError, ValueError, OverflowError):
            amount = before = after = math.nan
        if (
            str(row.get("uid") or "") != referrer_uid
            or str(row.get("reason") or "") != "referral_success_bonus"
            or not math.isfinite(amount)
            or not math.isclose(amount, SUCCESS_REFERRAL_CREDITS, rel_tol=0.0, abs_tol=1e-9)
            or not math.isfinite(before)
            or not math.isfinite(after)
            or not math.isclose(before + amount, after, rel_tol=0.0, abs_tol=1e-9)
        ):
            raise ValueError("REFERRAL_CREDITS_IDEMPOTENCY_CONFLICT")

    if require_complete and (len(points_matches) != 1 or len(credits_matches) != 1):
        raise ValueError("REFERRAL_REWARD_LEDGER_INCOMPLETE")

    return {
        "points_recorded": len(points_matches) == 1,
        "credits_recorded": len(credits_matches) == 1,
        "points_key": points_key,
        "credits_key": credits_key,
    }


def recover_persisted_referral(referred_uid):
    """Retry rewards for a completed, already-persisted referral relationship.

    This function never creates or reassigns attribution. It uses the stored
    referred_by UID and stable reward keys, verifies the two authoritative
    ledgers, then atomically records completion and clears only the matching
    pending referral. Repeated and concurrent calls are safe.
    """
    referred_uid = str(referred_uid or "").strip()
    if not referred_uid:
        raise ValueError("INVALID_REFERRED_UID")

    db = state_manager.load_db()
    if not isinstance(db, dict):
        raise ValueError("REFERRAL_DB_UNREADABLE")
    users = db.get("users")
    if not isinstance(users, dict):
        raise ValueError("REFERRAL_USERS_UNREADABLE")

    referred = users.get(referred_uid)
    if not isinstance(referred, dict):
        return {"status": "NO_PERSISTED_REFERRAL", "referred_uid": referred_uid}
    referral = referred.get("referral")
    referrer_uid = str(referral.get("referred_by") or "").strip() if isinstance(referral, dict) else ""
    if not referrer_uid:
        return {"status": "NO_PERSISTED_REFERRAL", "referred_uid": referred_uid}
    if referrer_uid == referred_uid:
        raise ValueError("INVALID_REFERRAL")
    if referred.get("joined") is not True:
        return {"status": "JOIN_NOT_COMPLETED", "referred_uid": referred_uid}
    if not isinstance(users.get(referrer_uid), dict):
        raise ValueError("REFERRAL_REFERRER_MISSING")

    pending = db.get("pending_referrals")
    if isinstance(pending, dict):
        pending_referrer = pending.get(referred_uid)
        if pending_referrer and str(pending_referrer) != referrer_uid:
            raise ValueError("REFERRAL_PENDING_ATTRIBUTION_MISMATCH")

    # Detect a reused key pointing to another account or reward before granting
    # either leg. This matters because legacy reward callers may not request the
    # transaction service's detailed CONFLICT status.
    _reward_ledger_matches(db, referrer_uid, referred_uid, require_complete=False)

    settle_successful_referral(referrer_uid, referred_uid)

    # Require fresh, persisted accounting evidence before declaring success.
    verified_db = state_manager.load_db()
    if not isinstance(verified_db, dict):
        raise ValueError("REFERRAL_DB_UNREADABLE")
    verified_users = verified_db.get("users")
    verified_referred = verified_users.get(referred_uid) if isinstance(verified_users, dict) else None
    verified_referral = verified_referred.get("referral") if isinstance(verified_referred, dict) else None
    if (
        not isinstance(verified_referred, dict)
        or verified_referred.get("joined") is not True
        or not isinstance(verified_referral, dict)
        or str(verified_referral.get("referred_by") or "") != referrer_uid
    ):
        raise ValueError("REFERRAL_ATTRIBUTION_CHANGED_DURING_SETTLEMENT")
    evidence = _reward_ledger_matches(
        verified_db, referrer_uid, referred_uid, require_complete=True
    )

    def finalize(db2):
        current_users = db2.get("users")
        current_referred = current_users.get(referred_uid) if isinstance(current_users, dict) else None
        current_referral = current_referred.get("referral") if isinstance(current_referred, dict) else None
        if (
            not isinstance(current_referred, dict)
            or current_referred.get("joined") is not True
            or not isinstance(current_referral, dict)
            or str(current_referral.get("referred_by") or "") != referrer_uid
        ):
            raise ValueError("REFERRAL_ATTRIBUTION_CHANGED_DURING_FINALIZE")

        pending_map = db2.get("pending_referrals")
        if isinstance(pending_map, dict):
            pending_referrer = pending_map.get(referred_uid)
            if pending_referrer and str(pending_referrer) != referrer_uid:
                raise ValueError("REFERRAL_PENDING_ATTRIBUTION_MISMATCH")

        # Re-validate both authoritative reward ledgers against the same
        # locked DB snapshot that will receive the settlement marker. A prior
        # read cannot by itself authorize finalization if state changed later.
        current_evidence = _reward_ledger_matches(
            db2, referrer_uid, referred_uid, require_complete=True
        )
        if (
            current_evidence["points_key"] != evidence["points_key"]
            or current_evidence["credits_key"] != evidence["credits_key"]
        ):
            raise ValueError("REFERRAL_REWARD_EVIDENCE_CHANGED_DURING_FINALIZE")

        settlements = db2.setdefault(SETTLEMENTS_KEY, {})
        if not isinstance(settlements, dict):
            raise ValueError("REFERRAL_SETTLEMENTS_UNREADABLE")
        existing = settlements.get(referred_uid)
        was_settled = existing is not None
        if existing is not None:
            if (
                not isinstance(existing, dict)
                or str(existing.get("referrer_uid") or "") != referrer_uid
                or existing.get("points_idempotency_key") != evidence["points_key"]
                or existing.get("credits_idempotency_key") != evidence["credits_key"]
                or existing.get("status") != "SETTLED"
            ):
                raise ValueError("REFERRAL_SETTLEMENT_RECORD_CONFLICT")
        else:
            settlements[referred_uid] = {
                "referred_uid": referred_uid,
                "referrer_uid": referrer_uid,
                "points_idempotency_key": evidence["points_key"],
                "credits_idempotency_key": evidence["credits_key"],
                "status": "SETTLED",
                "settled_at": datetime.now(timezone.utc).isoformat(),
            }

        pending_map = db2.get("pending_referrals")
        if isinstance(pending_map, dict) and str(pending_map.get(referred_uid) or "") == referrer_uid:
            pending_map.pop(referred_uid, None)

        return {
            "status": "ALREADY_SETTLED" if was_settled else "SETTLED",
            "referred_uid": referred_uid,
            "referrer_uid": referrer_uid,
            "points": SUCCESS_REFERRAL_POINTS,
            "credits": SUCCESS_REFERRAL_CREDITS,
        }

    return state_manager.atomic_update(finalize)


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
