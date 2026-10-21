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
