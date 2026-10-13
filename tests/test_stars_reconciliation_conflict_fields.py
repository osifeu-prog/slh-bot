"""Stars reconciliation exposes only conflicting field names, not payment data."""

from types import SimpleNamespace
from unittest.mock import Mock

from core import stars_payment_authority, stars_price_authority
from store import fulfillment_recovery


def test_reconciliation_reports_conflicting_fields_without_exposing_raw_payload(monkeypatch):
    transaction = {
        "id": "charge-test-1",
        "amount": 100,
        "source": {
            "type": "user",
            "transaction_type": "invoice_payment",
            "user": {"id": 100},
            "invoice_payload": "credits_100_100",
        },
    }
    response = Mock()
    response.json.return_value = {
        "ok": True,
        "result": {"transactions": [transaction]},
    }
    response.raise_for_status.return_value = None

    monkeypatch.setenv("BOT_TOKEN", "test-token-not-real")
    monkeypatch.setattr(fulfillment_recovery.requests, "get", lambda *args, **kwargs: response)
    monkeypatch.setattr(
        stars_price_authority,
        "resolve_credit_pack",
        lambda credits, stars: SimpleNamespace(credits=credits, stars=stars),
    )
    monkeypatch.setattr(
        stars_payment_authority,
        "record_stars_payment",
        lambda **kwargs: {
            "status": "conflict",
            "credits": 0,
            "credits_applied": 0,
            "conflicting_fields": ["credits", "revenue.uid"],
        },
    )

    result = fulfillment_recovery.reconcile_telegram_stars()

    assert result["attempted"] == 1
    assert result["success"] == 0
    assert result["failed"] == 1
    assert result["details"][0]["status"] == "conflict"
    assert result["details"][0]["conflicting_fields"] == ["credits", "revenue.uid"]
    assert "raw_error" not in result["details"][0]
    assert "prompt" not in result["details"][0]


def test_reconciliation_handles_conflict_fields_from_late_revenue_write(monkeypatch):
    transaction = {
        "id": "charge-test-2",
        "amount": 100,
        "source": {
            "type": "user",
            "transaction_type": "invoice_payment",
            "user": {"id": 100},
            "invoice_payload": "credits_100_100",
        },
    }
    response = Mock()
    response.json.return_value = {
        "ok": True,
        "result": {"transactions": [transaction]},
    }
    response.raise_for_status.return_value = None

    monkeypatch.setenv("BOT_TOKEN", "test-token-not-real")
    monkeypatch.setattr(fulfillment_recovery.requests, "get", lambda *args, **kwargs: response)
    monkeypatch.setattr(
        stars_price_authority,
        "resolve_credit_pack",
        lambda credits, stars: SimpleNamespace(credits=credits, stars=stars),
    )
    monkeypatch.setattr(
        stars_payment_authority,
        "record_stars_payment",
        lambda **kwargs: {
            "status": "duplicate",
            "revenue_status": "conflict",
            "revenue_conflicting_fields": ["amount"],
        },
    )

    result = fulfillment_recovery.reconcile_telegram_stars()

    assert result["failed"] == 1
    assert result["details"][0]["conflicting_fields"] == ["amount"]
