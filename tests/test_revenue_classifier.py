from decimal import Decimal

from core.revenue_classifier import classify, classify_all, eligible_revenue_total


POLICY = {
    "telegram_stars",
    "telegram_stars_item",
    "telegram_stars_subscription",
}


def test_verified_real_payment_is_eligible():
    entry = {
        "reference": "stxg_real_100",
        "source": "telegram_stars",
        "amount": 100,
        "currency": "XTR",
        "uid": "501",
    }
    result = classify(
        entry,
        verified_charge_ids={"stxg_real_100"},
        test_legacy_charge_ids=set(),
        policy_allowed_sources=POLICY,
    )

    assert result["observed"] == {
        "source": "telegram_stars",
        "amount": 100,
        "currency": "XTR",
        "uid": "501",
    }
    assert result["verified"] is True
    assert result["test_legacy"] is False
    assert result["policy_eligible"] is True
    assert result["eligible"] is True


def test_boundary_test_entry_is_not_verified_or_eligible():
    entry = {
        "reference": "boundary-test-xtr",
        "source": "telegram_stars",
        "amount": 100,
    }
    result = classify(
        entry,
        verified_charge_ids=set(),
        test_legacy_charge_ids={"boundary-test-xtr"},
        policy_allowed_sources=POLICY,
    )

    assert result["verified"] is False
    assert result["test_legacy"] is True
    assert result["policy_eligible"] is True
    assert result["eligible"] is False


def test_verified_entry_marked_test_legacy_is_ineligible():
    entry = {
        "reference": "stx_test_1",
        "source": "telegram_stars",
        "amount": 100,
    }
    result = classify(
        entry,
        verified_charge_ids={"stx_test_1"},
        test_legacy_charge_ids={"stx_test_1"},
        policy_allowed_sources=POLICY,
    )

    assert result["verified"] is True
    assert result["test_legacy"] is True
    assert result["policy_eligible"] is True
    assert result["eligible"] is False


def test_verified_entry_outside_policy_is_ineligible():
    entry = {
        "reference": "stxg_real_internal",
        "source": "internal:commission",
        "amount": 0.1,
    }
    result = classify(
        entry,
        verified_charge_ids={"stxg_real_internal"},
        test_legacy_charge_ids=set(),
        policy_allowed_sources=POLICY,
    )

    assert result["verified"] is True
    assert result["test_legacy"] is False
    assert result["policy_eligible"] is False
    assert result["eligible"] is False


def test_eligible_revenue_total_matches_verified_real_stars():
    refs = [
        "stx-100",
        "stx-499",
        "stx-199-a",
        "stx-199-b",
        "stx-100-b",
        "stx-25",
    ]
    db = {
        "revenue_ledger": [
            {"reference": refs[0], "source": "telegram_stars", "amount": 100, "currency": "XTR"},
            {"reference": refs[1], "source": "telegram_stars_subscription", "amount": 499, "currency": "XTR"},
            {"reference": refs[2], "source": "telegram_stars_item", "amount": 199, "currency": "XTR"},
            {"reference": refs[3], "source": "telegram_stars_item", "amount": 199, "currency": "XTR"},
            {"reference": refs[4], "source": "telegram_stars", "amount": 100, "currency": "XTR"},
            {"reference": refs[5], "source": "telegram_stars_item", "amount": 25, "currency": "XTR"},
            {"reference": "boundary-test-xtr", "source": "telegram_stars", "amount": 100, "currency": "XTR"},
        ]
    }

    results = classify_all(
        db,
        verified=set(refs),
        test_legacy={"boundary-test-xtr"},
        policy_allowed=POLICY,
    )

    assert len(results) == 7
    assert sum(1 for result in results if result["eligible"]) == 6
    assert eligible_revenue_total(
        db,
        verified=set(refs),
        test_legacy={"boundary-test-xtr"},
        policy_allowed=POLICY,
    ) == Decimal("1122")
