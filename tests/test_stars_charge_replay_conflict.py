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


def base_revenue(uid="100", amount=100, currency="XTR"):
    return {
        "timestamp": "2026-01-01T00:00:01+00:00",
        "source": "telegram_stars",
        "amount": amount,
        "currency": currency,
        "reference": "charge-immutable-1",
        "uid": uid,
        "meta": {
            "kind": "telegram_stars_gross",
            "payment_meta": {},
            "provider_charge_id": "provider-charge-1",
        },
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
        "revenue_ledger": [base_revenue()],
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


def test_revenue_conflict_blocks_new_credit_grant(monkeypatch):
    db = make_db()
    db["transactions"] = []
    db["ledger"] = []
    db["revenue_ledger"][0]["amount"] = 99
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

    assert result["status"] == "conflict"
    assert result["conflict_domain"] == "revenue_ledger"
    assert "amount" in result["conflicting_fields"]
    assert db == before


def test_missing_revenue_is_recovered_without_recredit(monkeypatch):
    db = make_db()
    db["revenue_ledger"] = []
    before_user = copy.deepcopy(db["users"])
    before_transactions = copy.deepcopy(db["transactions"])
    before_ledger = copy.deepcopy(db["ledger"])
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
    assert db["users"] == before_user
    assert db["transactions"] == before_transactions
    assert db["ledger"] == before_ledger
    assert len(db["revenue_ledger"]) == 1
    assert db["revenue_ledger"][0]["amount"] == 100
    assert db["revenue_ledger"][0]["currency"] == "XTR"
    assert db["revenue_ledger"][0]["uid"] == "100"


def test_new_payment_updates_credits_and_revenue_in_one_atomic_mutation(monkeypatch):
    db = make_db()
    db["transactions"] = []
    db["ledger"] = []
    db["revenue_ledger"] = []
    before_balance = db["users"]["100"]["wallet"]["credits"]
    monkeypatch.setattr(
        economy_service.state_manager,
        "atomic_update",
        lambda mutate: mutate(db),
    )

    result = economy_service.record_stars_payment(
        uid="100",
        credits=250,
        stars_paid=150,
        currency="XTR",
        telegram_payment_charge_id="charge-new-2",
        provider_payment_charge_id="provider-new-2",
        meta={"source": "test"},
    )

    assert result["status"] == "applied"
    assert db["users"]["100"]["wallet"]["credits"] == before_balance + 250
    assert len(db["transactions"]) == 1
    assert len(db["ledger"]) == 1
    assert len(db["revenue_ledger"]) == 1
    assert db["revenue_ledger"][0]["amount"] == 150
    assert db["revenue_ledger"][0]["currency"] == "XTR"
    assert db["revenue_ledger"][0]["uid"] == "100"
    assert db["revenue_ledger"][0]["reference"] == "charge-new-2"
