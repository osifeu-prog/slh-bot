"""Telegram Stars payment authorities."""

import time
from datetime import datetime
from zoneinfo import ZoneInfo

import state_manager

from core import economy_service
from core import revenue_ledger
from core.vip_fulfillment import apply_vip_benefits, is_launch_offer_open
from core.stars_price_authority import (
    TELEGRAM_STARS_CURRENCY,
    VIP_MONTHLY_STARS,
    VIP_ANNUAL_STARS,
    VIP_SUBSCRIPTION_PERIOD,
    VIP_ANNUAL_PERIOD,
)




def _record_revenue(*, source: str, amount: int, reference: str, uid: str, meta: dict):
    return revenue_ledger.record(
        source=source,
        amount=int(amount),
        currency=TELEGRAM_STARS_CURRENCY,
        reference=str(reference),
        uid=str(uid),
        meta=dict(meta),
    )


def record_stars_payment(**kwargs):
    """Validate and atomically account for a confirmed Telegram Stars payment."""
    currency = str(kwargs.get("currency", ""))
    if currency != TELEGRAM_STARS_CURRENCY:
        raise ValueError("INVALID_PAYMENT_CURRENCY")

    result = economy_service.record_stars_payment(**kwargs)

    if result.get("status") in {"applied", "duplicate"}:
        revenue_result = _record_revenue(
            source="telegram_stars",
            amount=int(kwargs.get("stars_paid", 0)),
            reference=str(kwargs.get("telegram_payment_charge_id", "")),
            uid=str(kwargs.get("uid", "")),
            meta={
                "kind": "telegram_stars_gross",
                "payment_meta": dict(kwargs.get("meta") or {}),
                "provider_charge_id": kwargs.get("provider_payment_charge_id"),
            },
        )
        if isinstance(revenue_result, dict) and revenue_result.get("status") == "conflict":
            # The wallet transaction has already committed in the primary
            # authority; preserve it and surface the accounting conflict for
            # operator review rather than retrying or rewriting revenue.
            result = dict(result)
            result["revenue_status"] = "conflict"
            result["revenue_conflicting_fields"] = list(
                revenue_result.get("conflicting_fields") or []
            )

    return result


def _set_fulfillment_status(charge_id: str, status: str, bundle: dict | None = None):
    def mutate(db):
        record = db.setdefault("vip_subscriptions", {}).get(str(charge_id))
        if record is None:
            raise KeyError("VIP_SUBSCRIPTION_NOT_FOUND")
        record["fulfillment_status"] = str(status)
        if bundle is not None:
            record["bundle"] = dict(bundle)
        return dict(record)

    return state_manager.atomic_update(mutate)


def record_vip_subscription_payment(
    *,
    uid,
    stars_paid,
    charge_id,
    recurring=False,
    first_recurring=False,
    now=None,
    annual=False,
):
    """Activate monthly or annual VIP and safely fulfill qualifying launch benefits."""
    uid = str(uid).strip()
    charge_id = str(charge_id or "").strip()
    try:
        stars_paid = int(stars_paid)
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_VIP_STARS_AMOUNT") from exc

    if not uid:
        raise ValueError("INVALID_USER_ID")
    if not charge_id:
        raise ValueError("INVALID_CHARGE_ID")
    annual = bool(annual)
    expected_stars = VIP_ANNUAL_STARS if annual else VIP_MONTHLY_STARS
    subscription_period = VIP_ANNUAL_PERIOD if annual else VIP_SUBSCRIPTION_PERIOD
    period_kind = "vip_annual" if annual else "vip_monthly"
    if stars_paid != expected_stars:
        raise ValueError("INVALID_VIP_STARS_AMOUNT")

    now = int(time.time() if now is None else now)
    now_dt = datetime.fromtimestamp(now, tz=ZoneInfo("Asia/Jerusalem"))

    def activate_and_mark(db):
        users = db.get("users", {})
        orders = db.get("vip_subscriptions", {})
        if not isinstance(users, dict) or not isinstance(orders, dict):
            return None, False, ["state_shape"]

        revenue_args = {
            "source": "telegram_stars_subscription",
            "amount": stars_paid,
            "currency": TELEGRAM_STARS_CURRENCY,
            "reference": charge_id,
            "uid": uid,
            "meta": {
                "kind": period_kind,
                "subscription_period": subscription_period,
                "period_months": 12 if annual else 1,
            },
        }

        existing = orders.get(charge_id)
        if existing is not None:
            if not isinstance(existing, dict):
                return None, False, ["subscription_shape"]
            conflicts = []
            if str(existing.get("uid")) != uid:
                conflicts.append("uid")
            try:
                stored_stars = int(existing.get("stars_paid"))
            except (TypeError, ValueError, OverflowError):
                stored_stars = None
            if stored_stars != stars_paid:
                conflicts.append("stars_paid")
            if bool(existing.get("annual", False)) != annual:
                conflicts.append("annual")
            conflicts.extend(
                "revenue." + field
                for field in revenue_ledger.conflicting_fields_in_db(db, **revenue_args)
            )
            if conflicts:
                return None, False, sorted(set(conflicts))

            # A legitimate replay can recover a missing revenue event atomically,
            # but conflicting immutable fields stop before any subscription mutation.
            revenue_result = revenue_ledger.record_in_db(db, **revenue_args)
            if revenue_result.get("status") == "conflict":
                conflicts = [
                    "revenue." + field
                    for field in revenue_result.get("conflicting_fields", [])
                ]
                return None, False, conflicts
            return dict(existing), False, []

        existing_user = users.get(uid, {})
        if not isinstance(existing_user, dict):
            return None, False, ["user_shape"]
        user = dict(existing_user)
        permissions_value = existing_user.get("permissions", [])
        if permissions_value is None:
            permissions_value = []
        if not isinstance(permissions_value, list):
            return None, False, ["permissions_shape"]
        permissions = list(permissions_value)

        previous = int(existing_user.get("vip_access_until", 0) or 0)
        start = max(now, previous)
        until = start + subscription_period
        vip_bundle = existing_user.get("vip_bundle")
        vip_bundle = vip_bundle if isinstance(vip_bundle, dict) else {}
        already_qualified = bool(
            existing_user.get("vip_launch_offer_qualified")
            or vip_bundle.get("launch_offer_qualified")
        )
        launch_offer_qualified = already_qualified or is_launch_offer_open(now_dt)

        revenue_args["meta"] = {
            **revenue_args["meta"],
            "launch_offer_qualified": bool(launch_offer_qualified),
        }
        revenue_conflicts = revenue_ledger.conflicting_fields_in_db(db, **revenue_args)
        if revenue_conflicts:
            return None, False, ["revenue." + field for field in revenue_conflicts]
        revenue_result = revenue_ledger.record_in_db(db, **revenue_args)
        if revenue_result.get("status") == "conflict":
            return None, False, [
                "revenue." + field
                for field in revenue_result.get("conflicting_fields", [])
            ]

        if "vip_access" not in permissions:
            permissions.append("vip_access")
        user["permissions"] = permissions
        if launch_offer_qualified:
            user["vip_launch_offer_qualified"] = True

        record = {
            "charge_id": charge_id,
            "uid": uid,
            "stars_paid": stars_paid,
            "started_at": now,
            "expires_at": until,
            "status": "ACTIVE",
            "recurring": bool(recurring),
            "first_recurring": bool(first_recurring),
            "annual": annual,
            "period_months": 12 if annual else 1,
            "launch_offer_qualified": bool(launch_offer_qualified),
            "fulfillment_status": "pending",
        }
        user["vip_access_until"] = until
        users[uid] = user
        db["vip_subscriptions"] = orders
        orders[charge_id] = record
        return dict(record), True, []
    record, created, conflict_fields = state_manager.atomic_update(activate_and_mark)
    if conflict_fields:
        return {
            "status": "conflict",
            "created": False,
            "charge_id": charge_id,
            "conflicting_fields": list(conflict_fields),
            "fulfillment_status": "blocked",
        }
    if not isinstance(record, dict):
        return {
            "status": "conflict",
            "created": False,
            "charge_id": charge_id,
            "conflicting_fields": ["subscription_state_unavailable"],
            "fulfillment_status": "blocked",
        }

    # Reconcile referral rewards and WhatsApp cashback on every legitimate
    # replay. Each reward has its own idempotency key, so this is safe even
    # after a previous payment record succeeded but a reward write was pending.
    loyalty_rewards = {}
    try:
        from core.commerce_loyalty import grant_whatsapp_cashback
        loyalty_rewards["whatsapp_cashback"] = grant_whatsapp_cashback(
            uid, f"vip:{charge_id}", stars_paid, TELEGRAM_STARS_CURRENCY,
            sku="vip_annual" if annual else "vip_monthly",
        )
    except Exception as exc:
        loyalty_rewards["whatsapp_cashback"] = {
            "status": "PENDING", "error": type(exc).__name__
        }
    try:
        from core.commerce_loyalty import settle_referred_vip_purchase
        loyalty_rewards["referral"] = settle_referred_vip_purchase(
            uid, charge_id, stars_paid
        )
    except Exception as exc:
        loyalty_rewards["referral"] = {
            "status": "PENDING", "error": type(exc).__name__
        }

    # A completed replay is a no-op: do not re-run VIP fulfillment or record
    # subscription revenue a second time. Loyalty rewards above are independently
    # idempotent and can be reconciled on replay.
    if not created and str(record.get("fulfillment_status", "pending")) == "completed":
        return {
            "status": "duplicate",
            "created": False,
            "record": record,
            "launch_offer_qualified": bool(record.get("launch_offer_qualified")),
            "fulfillment_status": "completed",
            "bundle": record.get("bundle"),
            "loyalty_rewards": loyalty_rewards,
        }

    bundle = apply_vip_benefits(
        uid=uid,
        charge_id=charge_id,
        launch_offer_qualified=bool(record.get("launch_offer_qualified")),
    )
    fulfillment_status = str(bundle.get("status", "pending"))

    try:
        record = _set_fulfillment_status(charge_id, fulfillment_status, bundle)
    except Exception:
        # Payment and subscription are already safely recorded. A subsequent
        # replay will retry bundle fulfillment without recharging.
        fulfillment_status = "pending"

    return {
        "status": "applied" if created else "duplicate",
        "created": created,
        "record": record,
        "launch_offer_qualified": bool(record.get("launch_offer_qualified")),
        "fulfillment_status": fulfillment_status,
        "bundle": bundle,
        "loyalty_rewards": loyalty_rewards,
    }
