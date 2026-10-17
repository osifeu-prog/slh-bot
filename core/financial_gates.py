"""Fail-closed availability gates for external payment entrypoints."""

import os


def stars_payments_open():
    """Allow new Telegram Stars invoices/pre-checkouts only by explicit opt-in."""
    return os.getenv("STARS_PAYMENTS_OPEN", "0").strip() == "1"
