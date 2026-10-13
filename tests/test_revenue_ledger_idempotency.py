"""Revenue ledger idempotency/conflict behavior using an in-memory DB only."""

import copy
import math

import pytest

from core import revenue_ledger


BASE_EVENT = {
    "timestamp": "2026-01-01T00:00:00+00:00",
    "source": "telegram_stars",
    "amount": 100.0,
    "currency": "XTR",
    "reference": "charge-immutable-1",
    "uid": "100",
    "meta": {"kind": "telegram_stars_gross"},
}


def _db():
    return {revenue_ledger.KEY: [copy.deepcopy(BASE_EVENT)]}


def _patch_db(monkeypatch, db):
    monkeypatch.setattr(
        revenue_ledger.state_manager,
        "atomic_update",
        lambda mutate: mutate(db),
    )


def test_exact_revenue_replay_is_duplicate_without_mutation(monkeypatch):
    db = _db()
    before = copy.deepcopy(db)
    _patch_db(monkeypatch, db)

    result = revenue_ledger.record(
        source="telegram_stars",
        amount=100,
        currency="XTR",
        reference="charge-immutable-1",
        uid="100",
    )

    assert result["status"] == "duplicate"
    assert db == before


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"amount": 90}, "amount"),
        ({"currency": "USD"}, "currency"),
        ({"uid": "200"}, "uid"),
    ],
)
def test_conflicting_revenue_replay_is_not_a_duplicate_or_mutation(
    monkeypatch, changes, field
):
    db = _db()
    before = copy.deepcopy(db)
    _patch_db(monkeypatch, db)
    request = {
        "source": "telegram_stars",
        "amount": 100,
        "currency": "XTR",
        "reference": "charge-immutable-1",
        "uid": "100",
    }
    request.update(changes)

    result = revenue_ledger.record(**request)

    assert result["status"] == "conflict"
    assert field in result["conflicting_fields"]
    assert db == before


def test_record_in_db_conflict_is_read_only():
    db = _db()
    before = copy.deepcopy(db)

    result = revenue_ledger.record_in_db(
        db,
        source="telegram_stars",
        amount=100,
        currency="XTR",
        reference="charge-immutable-1",
        uid="200",
    )

    assert result["status"] == "conflict"
    assert "uid" in result["conflicting_fields"]
    assert db == before


def test_conflict_preflight_is_read_only_and_does_not_block_other_reference():
    db = _db()
    before = copy.deepcopy(db)

    conflict = revenue_ledger.conflicting_fields_in_db(
        db,
        source="telegram_stars",
        amount=100,
        currency="XTR",
        reference="charge-immutable-1",
        uid="200",
    )
    other_reference = revenue_ledger.conflicting_fields_in_db(
        db,
        source="telegram_stars",
        amount=100,
        currency="XTR",
        reference="charge-new",
        uid="200",
    )

    assert conflict == ["uid"]
    assert other_reference == []
    assert db == before


def test_different_source_or_reference_records_normally(monkeypatch):
    db = _db()
    _patch_db(monkeypatch, db)

    result = revenue_ledger.record(
        source="telegram_stars_item",
        amount=100,
        currency="XTR",
        reference="charge-immutable-1",
        uid="100",
    )

    assert result["status"] == "recorded"
    assert len(db[revenue_ledger.KEY]) == 2


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), float("-inf"), True])
def test_invalid_nonfinite_or_boolean_amount_is_rejected(amount):
    with pytest.raises(ValueError, match="INVALID_REVENUE_AMOUNT"):
        revenue_ledger.record_in_db(
            _db(),
            source="telegram_stars",
            amount=amount,
            currency="XTR",
            reference="charge-invalid",
            uid="100",
        )
