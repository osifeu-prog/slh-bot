from copy import deepcopy
from datetime import datetime

import webapp


def _exchange_db():
    return {
        "users": {
            "buyer": {
                "wallet": {
                    "credits": 100.0,
                    "token_balance": 0.0,
                    "live_token_balance": 0.0,
                    "exchange_reserved_slh": 0.0,
                    "exchange_reserved_credits": 0.0,
                }
            }
        },
        "exchange_orders": {},
        "exchange_trades": [],
        "exchange_requests": {},
        "exchange_sequence": 0,
        "ledger": [],
    }


def _passing_execution_check(db):
    return {
        "ok": True,
        "execution_ready": True,
        "public_gate": "OPEN",
        "public_ready": True,
        "verdict": "OPEN",
        "order_book_integrity": True,
        "trade_integrity": True,
        "money_invariants": True,
        "open_orders": len(
            [o for o in db["exchange_orders"].values() if o.get("status") == "open"]
        ),
    }


def _wire_exchange_test(monkeypatch, db, check):
    import core.system_checks as system_checks
    import handlers.exchange_handler as exchange_handler

    monkeypatch.setattr(webapp, "authenticated_uid", lambda: "buyer")
    monkeypatch.setattr(webapp.state_manager, "atomic_update", lambda mutate: mutate(db))
    monkeypatch.setattr(
        exchange_handler,
        "require_public_open",
        lambda: (_ for _ in ()).throw(
            AssertionError("the stale public-gate guard must not short-circuit the fresh check")
        ),
    )
    monkeypatch.setattr(system_checks, "check_exchange_for_execution", check)
    return webapp.app.test_client()


def test_mini_app_order_has_fresh_canonical_check_from_pre_execution_snapshot(monkeypatch):
    db = _exchange_db()
    seen = []

    def check(snapshot):
        seen.append(deepcopy(snapshot))
        return _passing_execution_check(snapshot)

    client = _wire_exchange_test(monkeypatch, db, check)
    response = client.post(
        "/api/v1/exchange/order",
        json={
            "side": "buy",
            "amount": "10",
            "price": "1",
            "client_request_id": "fresh-check-pass-1",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    receipt = payload["execution_check"]
    assert receipt["status"] == "PASS"
    assert receipt["verdict"] == "OPEN"
    assert receipt["public_gate"] == "OPEN"
    assert receipt["execution_ready"] is True
    assert receipt["public_ready"] is True
    assert receipt["order_book_integrity"] is True
    assert receipt["trade_integrity"] is True
    assert receipt["money_invariants"] is True
    assert datetime.fromisoformat(receipt["checked_at"])
    assert len(seen) == 1
    assert seen[0]["exchange_orders"] == {}
    assert seen[0]["users"]["buyer"]["wallet"]["credits"] == 100.0
    assert payload["order_id"] in db["exchange_orders"]
    assert db["exchange_orders"][payload["order_id"]]["status"] == "open"


def test_mini_app_order_fresh_check_block_fails_closed_without_mutation(monkeypatch):
    db = _exchange_db()
    before = deepcopy(db)

    def blocked_check(snapshot):
        assert snapshot is db
        return {
            "ok": False,
            "execution_ready": False,
            "public_gate": "CLOSED",
            "public_ready": False,
            "verdict": "BLOCKED",
            "order_book_integrity": True,
            "trade_integrity": True,
            "money_invariants": True,
            "open_orders": 0,
            "detail": "public exchange gate is CLOSED",
        }

    client = _wire_exchange_test(monkeypatch, db, blocked_check)
    response = client.post(
        "/api/v1/exchange/order",
        json={
            "side": "buy",
            "amount": "10",
            "price": "1",
            "client_request_id": "fresh-check-block-1",
        },
    )

    assert response.status_code == 409
    payload = response.get_json()
    assert payload["code"] == "EXCHANGE_FRESH_CHECK_BLOCKED"
    receipt = payload["exchange_check"]
    assert receipt["status"] == "BLOCKED"
    assert receipt["verdict"] == "BLOCKED"
    assert receipt["public_gate"] == "CLOSED"
    assert receipt["execution_ready"] is False
    assert datetime.fromisoformat(receipt["checked_at"])
    assert db == before


def test_same_client_request_id_returns_original_receipt_without_duplicate_order(monkeypatch):
    db = _exchange_db()
    calls = []

    def check(snapshot):
        calls.append(deepcopy(snapshot))
        return _passing_execution_check(snapshot)

    client = _wire_exchange_test(monkeypatch, db, check)
    request = {
        "side": "buy",
        "amount": "10",
        "price": "1",
        "client_request_id": "fresh-check-idempotent-1",
    }

    first = client.post("/api/v1/exchange/order", json=request)
    second = client.post("/api/v1/exchange/order", json=request)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.get_json() == first.get_json()
    assert len(db["exchange_orders"]) == 1
    # Idempotent retries replay the first receipt; they are not new executions.
    assert len(calls) == 1
