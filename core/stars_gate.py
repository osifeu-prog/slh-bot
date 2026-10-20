"""Fail-closed gate for Telegram Stars store-item checkouts.

Only products with a verified, user-specific digital entitlement are allowlisted.
Emoji packs remain unavailable until real delivery assets/links are configured;
Agent OS remains unavailable until plugin fulfilment is verified as user-scoped.
This gate is separate from Credits top-ups, VIP subscriptions, and the Exchange.
Confirmed successful_payment callbacks must still be handled after checkout closes.
"""

import os

STORE_STARS_SALES_ENV = "STARS_STORE_SALES_OPEN"

# These SKUs have an existing, user-specific fulfilment authority:
# Academy enrolment for the three paid courses, and a user permission for Trade Pro.
# Do not add new IDs without tests proving the exact buyer receives the promised value.
SELLABLE_STORE_STARS_ITEM_IDS = frozenset({
    "course_ethereum",
    "course_slh_vs_eth_sol",
    "course_algo_trading",
    "trade_pro",
})


def store_stars_sales_open() -> bool:
    """Return true only when store-item Stars sales are explicitly enabled."""
    return os.getenv(STORE_STARS_SALES_ENV, "0").strip() == "1"


def store_stars_item_allowed(item_id) -> bool:
    """Return true only for reviewed SKUs with user-scoped, testable fulfilment."""
    return str(item_id or "").strip() in SELLABLE_STORE_STARS_ITEM_IDS


def store_stars_item_sales_open(item_id) -> bool:
    """Whether this SKU is eligible for a new Stars checkout under the global gate."""
    return store_stars_sales_open() and store_stars_item_allowed(item_id)


def require_store_stars_sales_open(item_id) -> None:
    """Fail closed at the final invoice-creation boundary, both globally and per SKU."""
    if not store_stars_sales_open():
        raise RuntimeError("STARS_STORE_SALES_CLOSED")
    if not store_stars_item_allowed(item_id):
        raise RuntimeError("STARS_STORE_ITEM_NOT_AVAILABLE")
