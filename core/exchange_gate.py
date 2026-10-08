"""Canonical public gate for the internal SLH/Credits exchange.

The gate is fail-closed: public order placement is disabled unless the
deployment explicitly sets SLH_EXCHANGE_PUBLIC_OPEN=1.
"""

from __future__ import annotations

import os

ENV_NAME = "SLH_EXCHANGE_PUBLIC_OPEN"


def public_open() -> bool:
    return os.getenv(ENV_NAME, "0").strip() == "1"


def require_public_open() -> None:
    if not public_open():
        raise ValueError("EXCHANGE_PUBLIC_CLOSED")
