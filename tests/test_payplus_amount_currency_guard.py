"""Fail-closed PayPlus transaction amount/currency verification tests."""

import pytest

from core import card_payment_service as cards


ORDER = {"order_id": "card:test", "page_request_uid": "page-test", "amount": 199.00}


def _provider_response(**fields):
    transaction = {"transaction_uid": "tx-test", "status": "approved"}
    transaction.update(fields)
    return {"data": {"transaction": transaction}}


@pytest.mark.parametrize(
    ("fields", "error"),
    [
        ({"currency_code": "ILS"}, "PAYPLUS_AMOUNT_MISSING"),
        ({"amount": "199.00"}, "PAYPLUS_CURRENCY_MISSING"),
        ({"amount": "198.99", "currency_code": "ILS"}, "PAYPLUS_AMOUNT_MISMATCH"),
        ({"amount": "199.00", "currency_code": "USD"}, "PAYPLUS_CURRENCY_MISMATCH"),
    ],
)
def test_provider_transaction_rejects_missing_or_mismatched_amount_currency(
    monkeypatch, fields, error
):
    monkeypatch.setattr(cards, "_post_payplus", lambda *_args, **_kwargs: _provider_response(**fields))
    with pytest.raises(ValueError, match=error):
        cards._verify_provider_transaction(ORDER, {})


def test_provider_transaction_accepts_exact_amount_and_ils(monkeypatch):
    monkeypatch.setattr(
        cards,
        "_post_payplus",
        lambda *_args, **_kwargs: _provider_response(amount="199.00", currency_code="ILS"),
    )
    result = cards._verify_provider_transaction(ORDER, {})
    assert result["verified"] is True
    assert result["transaction_uid"] == "tx-test"


def test_provider_transaction_rejects_missing_expected_order_amount(monkeypatch):
    monkeypatch.setattr(
        cards,
        "_post_payplus",
        lambda *_args, **_kwargs: _provider_response(amount="199.00", currency_code="ILS"),
    )
    with pytest.raises(ValueError, match="PAYPLUS_AMOUNT_MISSING"):
        cards._verify_provider_transaction({**ORDER, "amount": None}, {})


def test_fulfilled_callback_replay_must_verify_before_revenue_reconciliation(monkeypatch):
    order = {**ORDER, "status": "FULFILLED", "transaction_uid": "tx-test"}
    monkeypatch.setattr(cards, "_require_card_config", lambda: None)
    monkeypatch.setattr(cards, "_validate_callback", lambda *_args: True)
    monkeypatch.setattr(cards, "_find_order", lambda *_args: order)
    monkeypatch.setattr(
        cards,
        "_verify_provider_transaction",
        lambda *_args: (_ for _ in ()).throw(ValueError("PAYPLUS_AMOUNT_MISSING")),
    )
    from unittest.mock import Mock
    mocked_fulfill = Mock()
    monkeypatch.setattr(cards, "_fulfill", mocked_fulfill)
    with pytest.raises(ValueError, match="PAYPLUS_AMOUNT_MISSING"):
        cards.handle_payplus_callback({"more_info": "card:test"}, "signed", "PayPlus")
    mocked_fulfill.assert_not_called()


def test_fulfilled_callback_replay_rejects_different_transaction_uid(monkeypatch):
    order = {**ORDER, "status": "FULFILLED", "transaction_uid": "tx-original"}
    monkeypatch.setattr(cards, "_require_card_config", lambda: None)
    monkeypatch.setattr(cards, "_validate_callback", lambda *_args: True)
    monkeypatch.setattr(cards, "_find_order", lambda *_args: order)
    monkeypatch.setattr(
        cards,
        "_verify_provider_transaction",
        lambda *_args: {"verified": True, "transaction_uid": "tx-different"},
    )
    from unittest.mock import Mock
    mocked_fulfill = Mock()
    monkeypatch.setattr(cards, "_fulfill", mocked_fulfill)
    with pytest.raises(ValueError, match="PAYPLUS_TRANSACTION_UID_MISMATCH"):
        cards.handle_payplus_callback({"more_info": "card:test"}, "signed", "PayPlus")
    mocked_fulfill.assert_not_called()


def test_card_recovery_loop_starts_only_one_thread(monkeypatch):
    class FakeThread:
        instances = []

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.started = False
            self.instances.append(self)

        def start(self):
            self.started = True

        def is_alive(self):
            return self.started

    monkeypatch.setattr(cards, "_card_recovery_thread", None)
    monkeypatch.setattr(cards.threading, "Thread", FakeThread)
    first = cards.start_card_recovery_loop()
    second = cards.start_card_recovery_loop()
    assert first is second
    assert len(FakeThread.instances) == 1


def test_fulfilled_callback_replay_nonapproved_does_not_cancel_order(monkeypatch):
    order = {**ORDER, "status": "FULFILLED", "transaction_uid": "tx-test"}
    monkeypatch.setattr(cards, "_require_card_config", lambda: None)
    monkeypatch.setattr(cards, "_validate_callback", lambda *_args: True)
    monkeypatch.setattr(cards, "_find_order", lambda *_args: order)
    monkeypatch.setattr(
        cards,
        "_verify_provider_transaction",
        lambda *_args: (_ for _ in ()).throw(ValueError("PAYPLUS_PAYMENT_NOT_APPROVED")),
    )
    from unittest.mock import Mock
    update = Mock()
    release = Mock()
    fulfill = Mock()
    monkeypatch.setattr(cards, "_update_order", update)
    monkeypatch.setattr(cards, "_release_inventory", release)
    monkeypatch.setattr(cards, "_fulfill", fulfill)
    with pytest.raises(ValueError, match="PAYPLUS_PAYMENT_NOT_APPROVED"):
        cards.handle_payplus_callback({"more_info": "card:test"}, "signed", "PayPlus")
    update.assert_not_called()
    release.assert_not_called()
    fulfill.assert_not_called()
