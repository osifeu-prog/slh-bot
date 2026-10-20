"""Fail-closed gate for new Telegram Stars store-item checkouts.

This is intentionally separate from Credits top-ups, VIP subscriptions, and the
SLH Exchange gate. Confirmed successful_payment callbacks must still be handled
even when new store checkout is closed.
"""

import os

STORE_STARS_SALES_ENV = "STARS_STORE_SALES_OPEN"


def store_stars_sales_open() -> bool:
    """Return true only when store-item Stars sales are explicitly enabled."""
    return os.getenv(STORE_STARS_SALES_ENV, "0").strip() == "1"


def require_store_stars_sales_open() -> None:
    """Fail closed at the final invoice-creation boundary."""
    if not store_stars_sales_open():
        raise RuntimeError("STARS_STORE_SALES_CLOSED")
