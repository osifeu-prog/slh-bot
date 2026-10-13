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
        "revenue_ledger": [
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "source": "telegram_stars",
                "amount": 100.0,
                "currency": "XTR",
                "reference": "charge-immutable-1",
                "uid": "100",
                "meta": {"kind": "telegram_stars_gross"},
            }
        ],
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
    assert any(
        item == field or item.endswith("." + field)
        or (field == "stars_paid" and item == "revenue.amount")
        or (field == "currency" and item == "revenue.currency")
        for item in result["conflicting_fields"]
    )
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
    assert any(item == "uid" or item.endswith(".uid") for item in result["conflicting_fields"])
    assert db == before



def test_duplicate_charge_recovers_missing_revenue_without_recredit(monkeypatch):
    db = make_db()
    db.pop("revenue_ledger")
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
    assert db["users"]["100"]["wallet"]["credits"] == before["users"]["100"]["wallet"]["credits"]
    assert db["transactions"] == before["transactions"]
    assert db["ledger"] == before["ledger"]
    assert len(db["revenue_ledger"]) == 1
    assert db["revenue_ledger"][0]["reference"] == "charge-immutable-1"


def test_conflicting_revenue_event_blocks_new_payment_without_any_mutation(monkeypatch):
    db = make_db()
    db["transactions"] = []
    db["ledger"] = []
    db["users"]["100"]["wallet"]["credits"] = 50.0
    db["revenue_ledger"][0]["uid"] = "200"
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
    assert "revenue.uid" in result["conflicting_fields"]
    assert db == before



def test_reconciliation_replay_ignores_only_unavailable_provider_charge_id(monkeypatch):
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
        provider_payment_charge_id=None,
        provider_payment_charge_id_unavailable=True,
    )

    assert result["status"] == "duplicate"
    assert result["credits"] == 0
    assert db == before


def test_reconciliation_replay_still_rejects_amount_mismatch_when_provider_id_unavailable(monkeypatch):
    db = make_db()
    before = copy.deepcopy(db)
    monkeypatch.setattr(
        economy_service.state_manager,
        "atomic_update",
        lambda mutate: mutate(db),
    )

    result = economy_service.record_stars_payment(
        uid="100",
        credits=250,
        stars_paid=100,
        currency="XTR",
        telegram_payment_charge_id="charge-immutable-1",
        provider_payment_charge_id=None,
        provider_payment_charge_id_unavailable=True,
    )

    assert result["status"] == "conflict"
    assert "credits" in result["conflicting_fields"]
    assert db == before


def test_direct_replay_remains_strict_when_provider_id_unavailable_flag_is_not_set(monkeypatch):
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
        provider_payment_charge_id=None,
    )

    assert result["status"] == "conflict"
    assert "provider_payment_charge_id" in result["conflicting_fields"]
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
    assert "revenue.amount" in result["conflicting_fields"]
    assert db == before


def test_missing_revenue_is_recovered_without_recredit(monkeypatch):
    db = make_db()
    db["revenue_ledger"] = []
    before_users = copy.deepcopy(db["users"])
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
    assert db["users"] == before_users
    assert db["transactions"] == before_transactions
    assert db["ledger"] == before_ledger
    assert len(db["revenue_ledger"]) == 1
    event = db["revenue_ledger"][0]
    assert event["amount"] == 100
    assert event["currency"] == "XTR"
    assert event["uid"] == "100"
    assert event["reference"] == "charge-immutable-1"


def test_new_payment_updates_credits_and_revenue_atomically(monkeypatch):
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
    event = db["revenue_ledger"][0]
    assert event["amount"] == 150
    assert event["currency"] == "XTR"
    assert event["uid"] == "100"
    assert event["reference"] == "charge-new-2"
