#!/usr/bin/env python3
"""Regression tests for the Telegram Stars payment boundary."""
import sys

sys.path.insert(0, ".")

from handlers.payment_handler import STARS_PACKS, _resolve_stars_package
from core import stars_payment_authority


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS: {name}")


# Canonical packages must resolve only at their exact Stars price.
for pack_id, (stars, credits, _label) in STARS_PACKS.items():
    resolved = _resolve_stars_package(credits, stars)
    check(f"{pack_id} exact price accepted", resolved is not None and resolved[0] == pack_id)

# Wrong price, currency is handled by the caller, and unknown package values
# must not resolve to a credit grant.
check("100 credits at 99 Stars rejected", _resolve_stars_package(100, 99) is None)
check("500 credits at 500 Stars rejected", _resolve_stars_package(500, 500) is None)
check("1000 credits at 801 Stars rejected", _resolve_stars_package(1000, 801) is None)
check("unknown credits rejected", _resolve_stars_package(9999, 9999) is None)
check("malformed credits rejected", _resolve_stars_package("abc", 100) is None)
check("malformed Stars rejected", _resolve_stars_package(100, "abc") is None)

# The payment-path authority must reject non-Telegram-Stars currency before
# delegating to the atomic economy service.
try:
    stars_payment_authority.record_stars_payment(
        uid="test-user",
        credits=100,
        stars_paid=100,
        currency="USD",
        telegram_payment_charge_id="boundary-test-usd",
    )
except ValueError as exc:
    check("non-XTR authority rejection", str(exc) == "INVALID_PAYMENT_CURRENCY")
else:
    raise AssertionError("non-XTR authority rejection")

# A valid XTR request must still delegate to the existing atomic economy
# authority. Stub only the downstream call so this test has no DB side effect.
called = {}
original = stars_payment_authority.economy_service.record_stars_payment

def fake_record(**kwargs):
    called.update(kwargs)
    return {"status": "applied", "uid": kwargs["uid"], "credits": 100, "charge_id": kwargs["telegram_payment_charge_id"]}

stars_payment_authority.economy_service.record_stars_payment = fake_record
try:
    result = stars_payment_authority.record_stars_payment(
        uid="test-user",
        credits=100,
        stars_paid=100,
        currency="XTR",
        telegram_payment_charge_id="boundary-test-xtr",
    )
finally:
    stars_payment_authority.economy_service.record_stars_payment = original

check("XTR authority delegates", called.get("currency") == "XTR" and result["status"] == "applied")

print("PAYMENT BOUNDARY TESTS: PASS")
