#!/usr/bin/env python3
"""Regression tests for the Telegram Stars payment boundary."""
import sys

sys.path.insert(0, ".")

from handlers.payment_handler import STARS_PACKS, _resolve_stars_package


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

print("PAYMENT BOUNDARY TESTS: PASS")
