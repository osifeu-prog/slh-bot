"""Telegram Stars payment authority boundary.

This wrapper is the single payment-path entry point used by the Telegram
handler. It rejects non-XTR currency before delegating to the atomic economy
service, while preserving the existing idempotent transaction authority.
"""

from core import economy_service


TELEGRAM_STARS_CURRENCY = "XTR"


def record_stars_payment(**kwargs):
    """Validate the Telegram Stars currency before credit issuance."""
    currency = str(kwargs.get("currency", ""))
    if currency != TELEGRAM_STARS_CURRENCY:
        raise ValueError("INVALID_PAYMENT_CURRENCY")

    return economy_service.record_stars_payment(**kwargs)
