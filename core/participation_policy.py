"""Canonical configuration and activation gates for future SLH Participation."""

from __future__ import annotations

import os


ASSET = "SLH_INTERNAL"
TERM_DAYS = 365
DISTRIBUTION_RATIO = 0.80
ANNUAL_CAP_RATIO = 0.65
POLICY_VERSION = "1.0"


def _enabled(name: str) -> bool:
    return os.getenv(name, "0").strip() == "1"


def activation_status() -> dict:
    checks = {
        "feature_enabled": _enabled("SLH_PARTICIPATION_ENABLED"),
        "policy_approved": _enabled("SLH_PARTICIPATION_POLICY_APPROVED"),
        "accounting_approved": _enabled("SLH_PARTICIPATION_ACCOUNTING_APPROVED"),
        "legal_approved": _enabled("SLH_PARTICIPATION_LEGAL_APPROVED"),
        "asset_authority_ready": _enabled("SLH_PARTICIPATION_ASSET_AUTHORITY_READY"),
        "reserve_ready": _enabled("SLH_PARTICIPATION_RESERVE_READY"),
        "settlement_ready": _enabled("SLH_PARTICIPATION_SETTLEMENT_READY"),
    }
    active = all(checks.values())
    return {
        "active": active,
        "status": "ACTIVE" if active else "DISABLED",
        "checks": checks,
        "policy_version": POLICY_VERSION,
        "asset": ASSET,
        "term_days": TERM_DAYS,
        "distribution_ratio": DISTRIBUTION_RATIO,
        "annual_cap_ratio": ANNUAL_CAP_RATIO,
    }


def require_active() -> None:
    if not activation_status()["active"]:
        raise RuntimeError("PARTICIPATION_NOT_ACTIVE")


def snapshot() -> dict:
    return activation_status()
