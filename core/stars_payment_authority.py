"""Telegram Stars payment authority boundary.

Confirmed Stars payments update the canonical user economy. Revenue
observability is reconciled on both first processing and safe replay.
"""

from core import economy_service
from core import revenue_ledger


TELEGRAM_STARS_CURRENCY = "XTR"


def _record_revenue(kwargs):
    revenue_ledger.record(
        source="telegram_stars",
        amount=int(kwargs.get("stars_paid", 0)),
        currency=TELEGRAM_STARS_CURRENCY,
        reference=str(kwargs.get("telegram_payment_charge_id", "")),
        uid=kwargs.get("uid"),
        meta={"kind": "telegram_stars_gross"},
    )


def record_stars_payment(**kwargs):
    """Validate and atomically account for a confirmed Telegram Stars payment."""
    currency = str(kwargs.get("currency", ""))
    if currency != TELEGRAM_STARS_CURRENCY:
        raise ValueError("INVALID_PAYMENT_CURRENCY")

    result = economy_service.record_stars_payment(**kwargs)

    # Reconcile revenue after either first application or an idempotent
    # replay. revenue_ledger.record() is itself idempotent by source+reference.
    if result.get("status") in {"applied", "duplicate"}:
        _record_revenue(kwargs)

    return result
