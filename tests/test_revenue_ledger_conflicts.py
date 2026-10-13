"""Tests for immutable revenue-ledger replay semantics."""
import copy

import pytest

from core import revenue_ledger


def make_db(*, amount=100, currency="XTR", uid="100"):
    return {
        "revenue_ledger": [
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "source": "telegram_stars",
                "amount": amount,
                "currency": currency,
                "reference": "charge-1",
                "uid": uid,
                "meta": {"kind": "telegram_stars_gross"},
            }
        ]
    }


@pytest.mark.parametrize(
    ("changes", "expected_field"),
    [
        ({"amount": 99}, "amount"),
        ({"currency": "USD"}, "currency"),
        ({"uid": "200"}, "uid"),
    ],
)
def test_same_source_reference_with_conflicting_immutable_fields_is_conflict(
    monkeypatch, changes, expected_field
):
    db = make_db()
    before = copy.deepcopy(db)
    monkeypatch.setattr(
        revenue_ledger.state_manager,
        "atomic_update",
        lambda mutate: mutate(db),
    )

    payload = {
        "source": "telegram_stars",
        "amount": 100,
        "currency": "XTR",
        "reference": "charge-1",
        "uid": "100",
        "meta": {"kind": "telegram_stars_gross"},
    }
    payload.update(changes)

    result = revenue_ledger.record(**payload)

    assert result["status"] == "conflict"
    assert expected_field in result["conflicting_fields"]
    assert db == before


def test_exact_replay_is_duplicate_without_append(monkeypatch):
    db = make_db()
    before = copy.deepcopy(db)
    monkeypatch.setattr(
        revenue_ledger.state_manager,
        "atomic_update",
        lambda mutate: mutate(db),
    )

    result = revenue_ledger.record(
        source="telegram_stars",
        amount=100,
        currency="XTR",
        reference="charge-1",
        uid="100",
    )

    assert result["status"] == "duplicate"
    assert db == before


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), float("-inf"), True, 0, -1])
def test_invalid_nonfinite_or_nonpositive_revenue_amount_rejected(amount):
    with pytest.raises(ValueError, match="INVALID_REVENUE_AMOUNT"):
        revenue_ledger.record(
            source="telegram_stars",
            amount=amount,
            currency="XTR",
            reference="charge-invalid",
            uid="100",
        )


def test_malformed_revenue_ledger_fails_closed(monkeypatch):
    db = {"revenue_ledger": {"bad": "shape"}}
    before = copy.deepcopy(db)
    monkeypatch.setattr(
        revenue_ledger.state_manager,
        "atomic_update",
        lambda mutate: mutate(db),
    )

    result = revenue_ledger.record(
        source="telegram_stars",
        amount=100,
        currency="XTR",
        reference="charge-1",
        uid="100",
    )

    assert result["status"] == "conflict"
    assert result["conflicting_fields"] == ["ledger_shape"]
    assert db == before
