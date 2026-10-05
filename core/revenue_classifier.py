"""Pure, evidence-based revenue classification for Participation callers.

This module never infers payment truth. Callers provide:
- verified_charge_ids from Stars reconciliation
- test_legacy_charge_ids from the same reconciliation layer
- policy_allowed_sources from the active policy

The classifier only combines those facts.
"""

from __future__ import annotations

from decimal import Decimal


def classify(
    entry: dict,
    *,
    verified_charge_ids: set,
    test_legacy_charge_ids: set,
    policy_allowed_sources: set,
) -> dict:
    """Classify one revenue entry without heuristics or side effects."""
    ref = str(entry.get("reference", ""))
    source = str(entry.get("source", ""))

    observed = {
        "source": source,
        "amount": entry.get("amount"),
        "currency": entry.get("currency"),
        "uid": entry.get("uid"),
    }
    verified = ref in verified_charge_ids
    test_legacy = ref in test_legacy_charge_ids
    policy_ok = source in policy_allowed_sources
    eligible = verified and not test_legacy and policy_ok

    return {
        "observed": observed,
        "verified": verified,
        "test_legacy": test_legacy,
        "policy_eligible": policy_ok,
        "eligible": eligible,
    }


def classify_all(
    db: dict,
    *,
    verified: set,
    test_legacy: set,
    policy_allowed: set,
) -> list[dict]:
    """Classify every revenue_ledger row."""
    rows = db.get("revenue_ledger", [])
    return [
        classify(
            row,
            verified_charge_ids=verified,
            test_legacy_charge_ids=test_legacy,
            policy_allowed_sources=policy_allowed,
        )
        for row in rows
        if isinstance(row, dict)
    ]


def eligible_revenue_total(
    db: dict,
    *,
    verified: set,
    test_legacy: set,
    policy_allowed: set,
) -> Decimal:
    """Return the Decimal total of revenue entries that are eligible."""
    total = Decimal("0")
    for result in classify_all(
        db,
        verified=verified,
        test_legacy=test_legacy,
        policy_allowed=policy_allowed,
    ):
        if result["eligible"]:
            total += Decimal(str(result["observed"]["amount"]))
    return total


def get_verified_charge_ids() -> set:
    """Fetch the canonical verified Stars charge IDs."""
    from core.stars_financial_truth import build_stars_financial_truth

    result = build_stars_financial_truth("0", owner=True)
    return set(result.get("owner", {}).get("matched_charge_ids", []))


def get_test_legacy_charge_ids() -> set:
    """Fetch the canonical test/legacy Stars charge IDs."""
    from core.stars_financial_truth import build_stars_financial_truth

    result = build_stars_financial_truth("0", owner=True)
    return set(result.get("owner", {}).get("test_legacy_charge_ids", []))
