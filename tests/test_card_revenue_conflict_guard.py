"""Card fulfillment must fail closed on conflicting revenue references."""

import copy

from core import card_payment_service as service


def _base_db(status="PAID"):
    return {
        "users": {"100": {"wallet": {}}},
        "card_orders": {
            "card:order-1": {
                "order_id": "card:order-1",
                "uid": "100",
                "item_id": "device_x",
                "item_name": "Device X",
                "amount": 120.0,
                "currency": "ILS",
                "provider": "payplus",
                "status": status,
                "transaction_uid": "payplus-tx-1",
                "inventory_reservation": {"item_id": "device_x", "quantity": 1},
                "fulfillment": None,
            }
        },
    }


def _patch_runtime(monkeypatch, db):
    monkeypatch.setattr(
        service.state_manager,
        "atomic_update",
        lambda mutate: mutate(db),
    )
    monkeypatch.setattr(
        service,
        "load_items",
        lambda: {"device_x": {"type": "hardware", "name": "Device X", "grant": {"kind": "device"}}},
    )
    monkeypatch.setattr(service, "_notify", lambda *args, **kwargs: None)


def test_conflicting_revenue_blocks_card_fulfillment_without_mutation(monkeypatch):
    db = _base_db()
    db["revenue_ledger"] = [
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "source": "payplus_card",
            "amount": 120.0,
            "currency": "ILS",
            "reference": "payplus-tx-1",
            "uid": "someone-else",
            "meta": {"order_id": "card:other", "item_id": "device_x", "provider": "payplus"},
        }
    ]
    before = copy.deepcopy(db)
    _patch_runtime(monkeypatch, db)
    grants = []
    monkeypatch.setattr(
        service,
        "apply_grant",
        lambda *args, **kwargs: grants.append((args, kwargs)) or {"ok": True},
    )

    result = service._fulfill(db["card_orders"]["card:order-1"])

    assert result["status"] == "revenue_conflict"
    assert grants == []
    assert db == before


def test_paid_card_order_records_revenue_before_fulfillment(monkeypatch):
    db = _base_db()
    _patch_runtime(monkeypatch, db)
    grants = []
    monkeypatch.setattr(
        service,
        "apply_grant",
        lambda *args, **kwargs: grants.append((args, kwargs)) or {"ok": True},
    )

    result = service._fulfill(db["card_orders"]["card:order-1"])

    assert result["status"] == "fulfilled"
    assert len(grants) == 1
    assert db["card_orders"]["card:order-1"]["status"] == "FULFILLED"
    assert len(db["revenue_ledger"]) == 1
    assert db["revenue_ledger"][0]["reference"] == "payplus-tx-1"
    assert db["revenue_ledger"][0]["uid"] == "100"


def test_fulfilled_card_replay_recovers_missing_revenue_without_grant(monkeypatch):
    db = _base_db(status="FULFILLED")
    db["card_orders"]["card:order-1"]["fulfillment"] = {"ok": True}
    _patch_runtime(monkeypatch, db)
    monkeypatch.setattr(
        service,
        "apply_grant",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("duplicate must not grant")),
    )

    result = service._fulfill(db["card_orders"]["card:order-1"])

    assert result["status"] == "duplicate"
    assert len(db["revenue_ledger"]) == 1
    assert db["revenue_ledger"][0]["reference"] == "payplus-tx-1"
    assert db["card_orders"]["card:order-1"]["status"] == "FULFILLED"
