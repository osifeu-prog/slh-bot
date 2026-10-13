"""Referral commission ledger integrity when Treasury is insufficient.

All tests use an in-memory database; no production state or payment provider
is accessed.
"""
import copy

from core import economy_service


def _db(treasury_balance=0.5, include_treasury=True):
    users = {
        "buyer": {
            "wallet": {"credits": 100.0},
            "referral": {"referred_by": "referrer"},
        },
        "referrer": {"wallet": {"credits": 50.0}},
    }
    if include_treasury:
        users[economy_service.TREASURY_UID] = {
            "wallet": {"credits": treasury_balance}
        }
    return {"users": users, "ledger": [], "transactions": []}


def _use_memory_db(monkeypatch, db):
    monkeypatch.setattr(
        economy_service.state_manager,
        "atomic_update",
        lambda mutate: mutate(db),
    )


def test_credit_purchase_with_insufficient_treasury_has_no_referral_credit(monkeypatch):
    db = _db(treasury_balance=0.5)
    _use_memory_db(monkeypatch, db)

    result = economy_service.purchase_item(
        uid="buyer", item="ask_credit", price=20, commission_rate=0.10
    )

    assert result["commission"] == 0
    assert db["users"]["buyer"]["wallet"]["credits"] == 80.0
    assert db["users"]["referrer"]["wallet"]["credits"] == 50.0
    assert db["users"][economy_service.TREASURY_UID]["wallet"]["credits"] == 0.5
    assert [row["reason"] for row in db["ledger"]] == ["purchase:ask_credit"]
    assert db.get("commissions", {}) == {}


def test_credit_purchase_with_missing_treasury_does_not_create_treasury(monkeypatch):
    db = _db(include_treasury=False)
    _use_memory_db(monkeypatch, db)

    result = economy_service.purchase_item(
        uid="buyer", item="ask_credit", price=20, commission_rate=0.10
    )

    assert result["commission"] == 0
    assert economy_service.TREASURY_UID not in db["users"]
    assert db["users"]["referrer"]["wallet"]["credits"] == 50.0
    assert [row["reason"] for row in db["ledger"]] == ["purchase:ask_credit"]


def test_stars_payment_with_insufficient_treasury_has_no_referral_credit(monkeypatch):
    db = _db(treasury_balance=1.0)
    before = copy.deepcopy(db)
    _use_memory_db(monkeypatch, db)

    result = economy_service.record_stars_payment(
        uid="buyer",
        credits=100,
        stars_paid=100,
        currency="XTR",
        telegram_payment_charge_id="test-charge-referral-1",
        commission_rate=0.10,
    )

    assert result["status"] == "applied"
    assert result["commission"] == 0
    assert db["users"]["buyer"]["wallet"]["credits"] == 200.0
    assert db["users"]["referrer"]["wallet"]["credits"] == 50.0
    assert db["users"][economy_service.TREASURY_UID]["wallet"]["credits"] == 1.0
    assert [row["reason"] for row in db["ledger"]] == ["payment:telegram_stars"]
    assert len(db["transactions"]) == len(before["transactions"]) + 1
    assert db.get("commissions", {}) == {}


def test_funded_credit_purchase_records_balanced_commission_ledger(monkeypatch):
    db = _db(treasury_balance=2.0)
    _use_memory_db(monkeypatch, db)

    result = economy_service.purchase_item(
        uid="buyer", item="ask_credit", price=20, commission_rate=0.10
    )

    assert result["commission"] == 2.0
    assert db["users"]["referrer"]["wallet"]["credits"] == 52.0
    assert db["users"][economy_service.TREASURY_UID]["wallet"]["credits"] == 0.0
    ref_event = next(row for row in db["ledger"] if row["reason"] == "referral:commission")
    treasury_event = next(row for row in db["ledger"] if row["reason"] == "referral:commission:debit")
    assert (ref_event["before"], ref_event["amount"], ref_event["after"]) == (50.0, 2.0, 52.0)
    assert treasury_event["before"] == 2.0
    assert treasury_event["amount"] == -2.0
    assert treasury_event["after"] == 0.0
    assert db["commissions"]["referrer"] == 2.0



def test_insufficient_treasury_does_not_create_missing_referrer_wallet_on_purchase(monkeypatch):
    db = _db(treasury_balance=0.5)
    db["users"]["referrer"].pop("wallet")
    _use_memory_db(monkeypatch, db)

    result = economy_service.purchase_item(
        uid="buyer", item="ask_credit", price=20, commission_rate=0.10
    )

    assert result["commission"] == 0
    assert "wallet" not in db["users"]["referrer"]
    assert [row["reason"] for row in db["ledger"]] == ["purchase:ask_credit"]
    assert db.get("commissions", {}) == {}


def test_insufficient_treasury_does_not_create_missing_referrer_wallet_on_stars(monkeypatch):
    db = _db(treasury_balance=0.5)
    db["users"]["referrer"].pop("wallet")
    _use_memory_db(monkeypatch, db)

    result = economy_service.record_stars_payment(
        uid="buyer",
        credits=100,
        stars_paid=100,
        currency="XTR",
        telegram_payment_charge_id="test-charge-missing-ref-wallet",
        commission_rate=0.10,
    )

    assert result["status"] == "applied"
    assert result["commission"] == 0
    assert "wallet" not in db["users"]["referrer"]
    assert [row["reason"] for row in db["ledger"]] == ["payment:telegram_stars"]
    assert db.get("commissions", {}) == {}
