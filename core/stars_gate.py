"""Fail-closed availability gate for new Telegram Stars checkouts.

A provider-confirmed successful_payment callback is intentionally not gated:
once Telegram has charged a user, that event must still be accounted for and
fulfilled/recovered safely even if new checkout is disabled.
"""
import os


def stars_payments_open() -> bool:
    return os.getenv("STARS_PAYMENTS_OPEN", "0").strip() == "1"


def require_stars_payments_open() -> None:
    if not stars_payments_open():
        raise RuntimeError("STARS_PAYMENTS_CLOSED")
