"""Regression tests for conflicting Telegram Stars charge replays.

These tests operate on an in-memory database only. They never call Telegram,
payment providers, Railway, or production state.
"""
import copy

import pytest

from core import economy_service


BASE_TX = {
    "uid": "100",
    "credits": 100.0,
    "stars_paid": 100,
    "currency": "XTR",
    "telegram_payment_charge_id": "charge-immutable-1",
    "provider_payment_charge_id": "provider-charge-1",
    "timestamp": "2026-01-01T00:00:00+00:00",
}


def make_db():
    return {
        "users": {
            "100": {"wallet": {"credits": 500.0}},
            "200": {"wallet": {"credits": 25.0}},
        },
        "transactions": [copy.deepcopy(BASE_TX)],
        "ledger": [
            {
                "uid": "100",
                "before": 400.0,
                "amount": 100.0,
                "after": 500.0,
                "reason": "payment:telegram_stars",
                "meta": {"charge_id": "charge-immutable-1"},
            }
        ],
    }


@pytest.mark.parametrize(
    ("uid", "changes", "field"),
    [
        ("200", {}, "uid"),
        ("100", {"credits": 250}, "credits"),
        ("100", {"stars_paid": 99}, "stars_paid"),
        ("100", {"currency": "USD"}, "currency"),
        ("100", {"provider_payment_charge_id": "provider-charge-2"}, "provider_payment_charge_id"),
        ("100", {"provider_payment_charge_id": None}, "provider_payment_charge_id"),
    ],
)
def test_conflicting_charge_replay_is_rejected_without_mutation(
    monkeypatch, uid, changes, field
):
    db = make_db()
    before = copy.deepcopy(db)
    monkeypatch.setattr(
        economy_service.state_manager,
        "atomic_update",
        lambda mutate: mutate(db),
    )

    request = {
        "uid": uid,
        "credits": 100,
        "stars_paid": 100,
        "currency": "XTR",
        "telegram_payment_charge_id": "charge-immutable-1",
        "provider_payment_charge_id": "provider-charge-1",
    }
    request.update(changes)

    result = economy_service.record_stars_payment(**request)

    assert result["status"] == "conflict"
    assert field in result["conflicting_fields"]
    assert result["credits"] == 0
    assert result["credits_applied"] == 0
    assert db == before


def test_exact_charge_replay_remains_duplicate_and_is_a_noop(monkeypatch):
    db = make_db()
    before = copy.deepcopy(db)
    monkeypatch.setattr(
        economy_service.state_manager,
        "atomic_update",
        lambda mutate: mutate(db),
    )

    result = economy_service.record_stars_payment(
        uid="100",
        credits=100,
        stars_paid=100,
        currency="XTR",
        telegram_payment_charge_id="charge-immutable-1",
        provider_payment_charge_id="provider-charge-1",
    )

    assert result["status"] == "duplicate"
    assert result["credits"] == 0
    assert db == before


def test_conflicting_replay_is_found_before_unknown_user_rejection(monkeypatch):
    db = make_db()
    before = copy.deepcopy(db)
    monkeypatch.setattr(
        economy_service.state_manager,
        "atomic_update",
        lambda mutate: mutate(db),
    )

    result = economy_service.record_stars_payment(
        uid="999",
        credits=100,
        stars_paid=100,
        currency="XTR",
        telegram_payment_charge_id="charge-immutable-1",
        provider_payment_charge_id="provider-charge-1",
    )

    assert result["status"] == "conflict"
    assert "uid" in result["conflicting_fields"]
    assert db == before
