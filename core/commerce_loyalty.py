"""Idempotent Credits cashback and paid-VIP referral rewards.

Cashback is eligible only for users who entered the commerce funnel through the
WhatsApp start link. Telegram Stars are converted to the cashback policy unit:
10% of Stars paid, rounded half-up to whole Credits. This is an internal reward,
not a statement that Credits and Stars are equivalent currencies.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import state_manager

WHATSAPP_CASHBACK_RATE = Decimal("0.10")
VIP_REFERRAL_COMMISSION_RATE = Decimal("0.10")
NEW_VIP_REFERRAL_BONUS_CREDITS = Decimal("25")


def _uid(value):
    text = str(value or "").strip()
    return text if text.isdigit() else None


def _money(value):
    if isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not amount.is_finite() or amount <= 0:
        return None
    return amount


def _round_credits(amount):
    return amount.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def _round_whole_credits(amount):
    return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _award_preflight(db, uid, amount, reason, idempotency_key):
    users = db.get("users")
    if not isinstance(users, dict) or not isinstance(users.get(uid), dict):
        return {"status": "USER_NOT_FOUND"}
    ledger = db.get("ledger")
    if ledger is None:
        ledger = []
    if not isinstance(ledger, list):
        return {"status": "STATE_INVALID"}

    expected = Decimal(str(amount))
    for row in ledger:
        if not isinstance(row, dict) or not isinstance(row.get("meta"), dict):
            continue
        if str(row["meta"].get("idempotency_key") or "") != idempotency_key:
            continue
        try:
            old_amount = Decimal(str(row.get("amount")))
        except (InvalidOperation, TypeError, ValueError):
            old_amount = None
        if (
            str(row.get("uid")) == uid
            and str(row.get("reason")) == reason
            and old_amount == expected
        ):
            return {"status": "DUPLICATE"}
        return {"status": "CONFLICT"}

    wallet = users[uid].get("wallet")
    if wallet is None:
        wallet = {}
    if not isinstance(wallet, dict):
        return {"status": "STATE_INVALID"}
    raw_before = wallet.get("credits", 0)
    if isinstance(raw_before, bool):
        return {"status": "STATE_INVALID"}
    try:
        before = Decimal(str(raw_before or 0))
    except (InvalidOperation, TypeError, ValueError):
        return {"status": "STATE_INVALID"}
    if not before.is_finite() or before < 0:
        return {"status": "STATE_INVALID"}
    return {"status": "READY", "before": before}


def _apply_award(db, uid, amount, reason, idempotency_key, details):
    preflight = _award_preflight(db, uid, amount, reason, idempotency_key)
    if preflight["status"] in {"DUPLICATE", "CONFLICT"}:
        return {**preflight, "uid": uid, "credits": str(amount)}
    if preflight["status"] != "READY":
        return preflight

    users = db["users"]
    user = users[uid]
    wallet = user.get("wallet")
    if wallet is None:
        wallet = {}
    before = preflight["before"]
    award = Decimal(str(amount))
    after = _round_credits(before + award)
    wallet["credits"] = float(after)
    user["wallet"] = wallet

    ledger = db.setdefault("ledger", [])
    meta = {
        **dict(details or {}),
        "idempotency_key": idempotency_key,
        "source": "commerce_loyalty",
    }
    ledger.append({
        "time": datetime.now(timezone.utc).isoformat(),
        "uid": uid,
        "before": float(before),
        "amount": float(award),
        "after": float(after),
        "reason": reason,
        "meta": meta,
    })
    return {
        "status": "APPLIED",
        "uid": uid,
        "credits": str(award),
        "balance_after": float(after),
        "idempotency_key": idempotency_key,
    }


def mark_whatsapp_store_touch(uid, referrer_uid=None, *, now=None):
    """Record a WhatsApp store touch without changing an existing referral owner."""
    uid = _uid(uid)
    referrer_uid = _uid(referrer_uid)
    if not uid:
        return {"status": "INVALID_USER_ID"}
    timestamp = str(now or datetime.now(timezone.utc).isoformat())

    def mutate(db):
        users = db.get("users")
        if not isinstance(users, dict) or not isinstance(users.get(uid), dict):
            return {"status": "USER_NOT_FOUND"}
        user = users[uid]
        touches = db.setdefault("whatsapp_store_touches", {})
        if not isinstance(touches, dict):
            return {"status": "STATE_INVALID"}
        existing = touches.get(uid)
        if isinstance(existing, dict):
            return {"status": "DUPLICATE", **existing}

        record = {
            "uid": uid,
            "referrer_uid": referrer_uid,
            "first_seen_at": timestamp,
            "source": "whatsapp_start_payload",
        }
        touches[uid] = record
        user.setdefault("whatsapp_store_touch", timestamp)
        user.setdefault("acquisition_channel", "whatsapp")
        return {"status": "APPLIED", **record}

    return state_manager.atomic_update(mutate)


def grant_whatsapp_cashback(uid, purchase_id, paid_amount, paid_currency, *, sku=None):
    """Grant cashback only for a completed order with verified per-purchase WhatsApp attribution."""
    uid = _uid(uid)
    purchase_id = str(purchase_id or "").strip()
    currency = str(paid_currency or "").strip().upper()
    sku_text = str(sku or "").strip().lower()
    if not uid or not purchase_id:
        return {"status": "INVALID_INPUT"}
    if any(marker in sku_text for marker in ("test", "smoke")):
        return {"status": "INELIGIBLE_TEST_SKU"}
    amount = _money(paid_amount)
    if amount is None or currency not in {"XTR", "STARS", "CREDITS"}:
        return {"status": "INVALID_PAYMENT_AMOUNT"}
    rate = amount * WHATSAPP_CASHBACK_RATE
    credits = _round_whole_credits(rate) if currency in {"XTR", "STARS"} else _round_credits(rate)
    if credits <= 0:
        return {"status": "NO_REWARD"}

    idempotency_key = f"whatsapp-cashback:{purchase_id}"
    details = {
        "purchase_id": purchase_id,
        "sku": str(sku or ""),
        "paid_amount": str(amount),
        "paid_currency": currency,
        "rate": str(WHATSAPP_CASHBACK_RATE),
        "rounding": "half_up_whole_credit_for_stars" if currency in {"XTR", "STARS"} else "8_decimal_credits",
    }

    def mutate(db):
        users = db.get("users")
        user = users.get(uid) if isinstance(users, dict) else None
        if not isinstance(user, dict):
            return {"status": "USER_NOT_FOUND"}
        # A user-level WhatsApp touch is not sufficient for a cashback award.
        # Require a trusted per-purchase record created only after a verified
        # WhatsApp intent has been correlated to the completed canonical order.
        attributions = db.get("whatsapp_purchase_attributions")
        attribution = attributions.get(purchase_id) if isinstance(attributions, dict) else None
        if not isinstance(attribution, dict):
            return {"status": "NOT_ELIGIBLE"}
        if (
            str(attribution.get("status") or "") != "VERIFIED_COMPLETED"
            or str(attribution.get("purchase_id") or "") != purchase_id
            or str(attribution.get("uid") or "") != uid
            or str(attribution.get("sku") or "") != str(sku or "")
            or not str(attribution.get("intent_id") or "").strip()
            or not str(attribution.get("provider_message_id_hash") or "").strip()
            or not str(attribution.get("completed_at") or "").strip()
        ):
            return {"status": "NOT_ELIGIBLE"}
        if str(attribution.get("paid_currency") or "").strip().upper() != currency:
            return {"status": "ATTRIBUTION_CONFLICT"}
        try:
            attributed_amount = Decimal(str(attribution.get("paid_amount")))
        except (InvalidOperation, TypeError, ValueError):
            return {"status": "ATTRIBUTION_CONFLICT"}
        if attributed_amount != amount:
            return {"status": "ATTRIBUTION_CONFLICT"}
        return _apply_award(
            db, uid, credits, "whatsapp:cashback", idempotency_key, details
        )

    return state_manager.atomic_update(mutate)


def settle_referred_vip_purchase(buyer_uid, charge_id, stars_paid):
    """Reward a valid referred VIP buyer and pay 10% of each VIP Stars charge in Credits."""
    buyer_uid = _uid(buyer_uid)
    charge_id = str(charge_id or "").strip()
    stars = _money(stars_paid)
    if not buyer_uid or not charge_id or stars is None:
        return {"status": "INVALID_INPUT"}
    if stars != stars.to_integral_value():
        return {"status": "INVALID_STARS_AMOUNT"}

    commission = _round_whole_credits(stars * VIP_REFERRAL_COMMISSION_RATE)
    newbie_key = f"vip-referral-newbie:{buyer_uid}"
    commission_key = f"vip-referral-commission:{charge_id}"

    def mutate(db):
        users = db.get("users")
        buyer = users.get(buyer_uid) if isinstance(users, dict) else None
        if not isinstance(buyer, dict):
            return {"status": "USER_NOT_FOUND"}
        referral = buyer.get("referral")
        referral = referral if isinstance(referral, dict) else {}
        referrer_uid = _uid(referral.get("referred_by"))
        if not referrer_uid or referrer_uid == buyer_uid:
            return {"status": "NOT_ELIGIBLE"}
        referrer = users.get(referrer_uid)
        if not isinstance(referrer, dict):
            return {"status": "REFERRER_NOT_FOUND"}

        # Preflight both awards before applying either: no partial buyer/referrer grant.
        newbie_preflight = _award_preflight(
            db, buyer_uid, NEW_VIP_REFERRAL_BONUS_CREDITS,
            "vip:referral_new_buyer_bonus", newbie_key,
        )
        commission_preflight = _award_preflight(
            db, referrer_uid, commission,
            "vip:referral_purchase_commission", commission_key,
        )
        allowed = {"READY", "DUPLICATE"}
        if newbie_preflight["status"] not in allowed:
            return {"status": newbie_preflight["status"], "phase": "new_buyer_bonus"}
        if commission_preflight["status"] not in allowed:
            return {"status": commission_preflight["status"], "phase": "referrer_commission"}

        newbie_result = (
            _apply_award(
                db, buyer_uid, NEW_VIP_REFERRAL_BONUS_CREDITS,
                "vip:referral_new_buyer_bonus", newbie_key,
                {"buyer_uid": buyer_uid, "referrer_uid": referrer_uid, "charge_id": charge_id},
            )
            if newbie_preflight["status"] == "READY"
            else {"status": "DUPLICATE", "credits": str(NEW_VIP_REFERRAL_BONUS_CREDITS)}
        )
        commission_result = (
            _apply_award(
                db, referrer_uid, commission,
                "vip:referral_purchase_commission", commission_key,
                {
                    "buyer_uid": buyer_uid,
                    "referrer_uid": referrer_uid,
                    "charge_id": charge_id,
                    "stars_paid": str(stars),
                    "rate": str(VIP_REFERRAL_COMMISSION_RATE),
                    "paid_currency": "XTR",
                    "reward_currency": "Credits",
                },
            )
            if commission_preflight["status"] == "READY"
            else {"status": "DUPLICATE", "credits": str(commission)}
        )
        applied = newbie_result.get("status") == "APPLIED" or commission_result.get("status") == "APPLIED"
        return {
            "status": "APPLIED" if applied else "DUPLICATE",
            "new_buyer_bonus": newbie_result,
            "referrer_commission": commission_result,
            "referrer_uid": referrer_uid,
        }

    return state_manager.atomic_update(mutate)
