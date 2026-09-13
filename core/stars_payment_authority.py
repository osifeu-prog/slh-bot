"""Telegram Stars payment authority boundary.

This wrapper is the single payment-path entry point used by the Telegram
handler. It rejects non-XTR currency before delegating to the atomic economy
service, while preserving the existing idempotent transaction authority.
"""

from core import economy_service
from core import revenue_ledger


TELEGRAM_STARS_CURRENCY = "XTR"


def record_stars_payment(**kwargs):
    """Validate and atomically account for a confirmed Telegram Stars payment."""
    currency = str(kwargs.get("currency", ""))
    if currency != TELEGRAM_STARS_CURRENCY:
        raise ValueError("INVALID_PAYMENT_CURRENCY")

    result = economy_service.record_stars_payment(**kwargs)

    # Revenue is recorded only after the Economy authority accepts the
    # payment. The charge id is the stable idempotency reference. This is
    # gross Stars payment value, not net cash/payout revenue.
    if result.get("status") == "applied":
        revenue_ledger.record(
            source="telegram_stars",
            amount=int(kwargs.get("stars_paid", 0)),
            currency=TELEGRAM_STARS_CURRENCY,
            reference=str(kwargs.get("telegram_payment_charge_id", "")),
            uid=kwargs.get("uid"),
            meta={"kind": "telegram_stars_gross"},
        )

    return result
