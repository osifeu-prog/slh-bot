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
    VIP_SUBSCRIPTION_PERIOD,
)




def _record_revenue(*, source: str, amount: int, reference: str, uid: str, meta: dict):
    revenue_ledger.record(
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
        _record_revenue(
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
):
    """Activate one VIP month and safely fulfill the launch bundle when eligible."""
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
    if stars_paid != VIP_MONTHLY_STARS:
        raise ValueError("INVALID_VIP_STARS_AMOUNT")

    now = int(time.time() if now is None else now)
    now_dt = datetime.fromtimestamp(now, tz=ZoneInfo("Asia/Jerusalem"))

    def activate_and_mark(db):
        orders = db.setdefault("vip_subscriptions", {})
        existing = orders.get(charge_id)
        if existing is not None:
            return existing, False

        users = db.setdefault("users", {})
        user = users.setdefault(uid, {})
        previous = int(user.get("vip_access_until", 0) or 0)
        start = max(now, previous)
        until = start + VIP_SUBSCRIPTION_PERIOD

        already_qualified = bool(
            user.get("vip_launch_offer_qualified")
            or user.get("vip_bundle", {}).get("launch_offer_qualified")
        )
        launch_offer_qualified = already_qualified or is_launch_offer_open(now_dt)

        perms = user.setdefault("permissions", [])
        if "vip_access" not in perms:
            perms.append("vip_access")

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
            "launch_offer_qualified": bool(launch_offer_qualified),
            "fulfillment_status": "pending",
        }
        orders[charge_id] = record
        user["vip_access_until"] = until
        return record, True

    record, created = state_manager.atomic_update(activate_and_mark)

    _record_revenue(
        source="telegram_stars_subscription",
        amount=stars_paid,
        reference=charge_id,
        uid=uid,
        meta={
            "kind": "vip_monthly",
            "subscription_period": VIP_SUBSCRIPTION_PERIOD,
            "launch_offer_qualified": bool(record.get("launch_offer_qualified")),
        },
    )

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
    }
