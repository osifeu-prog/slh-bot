from copy import deepcopy
from decimal import Decimal
from unittest import mock

import pytest

import handlers.exchange_handler as exchange


def _db():
    return {
        "users": {
            "seller": {
                "wallet": {
                    "token_balance": 10.0,
                    "live_token_balance": 10.0,
                    "exchange_reserved_slh": 0.0,
                    "exchange_reserved_credits": 0.0,
                    "credits": 0.0,
                }
            }
        },
        "exchange_orders": {},
        "exchange_trades": [],
        "exchange_requests": {},
        "slh_token_ledger": [],
    }


def test_order_entry_fails_closed_before_any_mutation_when_fresh_check_fails():
    db = _db()
    before = deepcopy(db)
    check = {
        "ok": False,
        "execution_ready": False,
        "public_gate": "CLOSED",
        "verdict": "BLOCKED",
        "public_ready": False,
        "order_book_integrity": True,
        "trade_integrity": True,
        "money_invariants": True,
        "open_orders": 0,
        "detail": "public exchange gate is CLOSED",
    }

    with mock.patch.object(exchange, "require_public_open"), mock.patch(
        "core.system_checks.check_exchange_for_execution",
        return_value=check,
    ) as fresh_check:
        with pytest.raises(exchange.ExchangeFreshCheckBlocked):
            exchange._place(
                db,
                "seller",
                "sell",
                Decimal("1"),
                Decimal("1"),
                "req-fresh-check-fail",
            )

    fresh_check.assert_called_once_with(db)
    assert db == before


def test_execution_receipt_requires_fresh_canonical_proof():
    passed = {
        "order_id": "O0000000001",
        "filled": "1.00000000",
        "remaining": "0.00000000",
        "status": "filled",
        "trade_ids": ["T0000000002"],
        "execution_check": {
            "status": "PASS",
            "checked_at": "2026-10-10T10:00:00+00:00",
            "public_gate": "OPEN",
            "verdict": "OPEN",
            "execution_ready": True,
            "public_ready": True,
            "order_book_integrity": True,
            "trade_integrity": True,
            "money_invariants": True,
            "open_orders_before": 0,
        },
    }

    receipt = exchange.format_execution_receipt("buy", passed)
    assert "Fresh canonical Exchange check: PASS" in receipt
    assert "checked_at (UTC): 2026-10-10T10:00:00+00:00" in receipt
    assert "Trade IDs: T0000000002" in receipt

    incomplete = exchange.format_execution_receipt("sell", {"order_id": "O2"})
    assert "Fresh canonical Exchange check: NOT VERIFIED" in incomplete
    assert "Receipt does not prove a passing fresh execution check." in incomplete
