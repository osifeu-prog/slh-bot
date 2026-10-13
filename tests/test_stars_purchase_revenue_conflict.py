"""Stars item replay conflicts must be rejected before fulfillment."""

import copy

from store import stars_purchase_service as service


def _items():
    return {
        "test_item": {
            "name": "Test item",
            "price_stars": 100,
            "type": "digital",
            "grant": {"kind": "test"},
        }
    }


def _patch_service(monkeypatch, db):
    items = _items()
    monkeypatch.setattr(service, "load_items", lambda: items)
    monkeypatch.setattr(
        service,
        "resolve_item_id",
        lambda item_id, catalog: item_id if item_id in catalog else None,
    )
    monkeypatch.setattr(service, "get_stars_price", lambda item_id: 100)
    monkeypatch.setattr(service.state_manager, "atomic_update", lambda mutate: mutate(db))


def test_conflicting_revenue_replay_does_not_create_order_or_fulfill(monkeypatch):
    db = {
        "users": {"buyer": {"wallet": {}}},
        "revenue_ledger": [
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "source": "telegram_stars_item",
                "amount": 100.0,
                "currency": "XTR",
                "reference": "charge-conflict-1",
                "uid": "someone-else",
                "meta": {"kind": "telegram_stars_item", "item_id": "test_item"},
            }
        ],
    }
    before = copy.deepcopy(db)
    _patch_service(monkeypatch, db)
    monkeypatch.setattr(
        service,
        "apply_grant",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not fulfill")),
    )

    result = service.purchase_item_with_stars(
        uid="buyer", item_id="test_item", stars_paid=100, charge_id="charge-conflict-1"
    )

    assert result["status"] == "CONFLICT"
    assert "revenue.uid" in result["conflicting_fields"]
    assert db == before


def test_replay_with_conflicting_existing_order_fields_does_not_mutate(monkeypatch):
    db = {
        "users": {
            "buyer": {"wallet": {}},
            "other": {"wallet": {}},
        },
        "star_item_orders": {
            "stars:charge-conflict-2": {
                "order_id": "stars:charge-conflict-2",
                "charge_id": "charge-conflict-2",
                "uid": "other",
                "item_id": "test_item",
                "stars_paid": 100,
                "status": "FULFILLED",
            }
        },
    }
    before = copy.deepcopy(db)
    _patch_service(monkeypatch, db)
    monkeypatch.setattr(
        service,
        "apply_grant",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not fulfill")),
    )

    result = service.purchase_item_with_stars(
        uid="buyer", item_id="test_item", stars_paid=100, charge_id="charge-conflict-2"
    )

    assert result["status"] == "CONFLICT"
    assert "uid" in result["conflicting_fields"]
    assert db == before


def test_fulfilled_replay_recovers_missing_revenue_without_granting_again(monkeypatch):
    db = {
        "users": {"buyer": {"wallet": {}}},
        "star_item_orders": {
            "stars:charge-recovery-1": {
                "order_id": "stars:charge-recovery-1",
                "charge_id": "charge-recovery-1",
                "uid": "buyer",
                "item_id": "test_item",
                "stars_paid": 100,
                "status": "FULFILLED",
                "fulfillment": {"ok": True},
            }
        },
    }
    _patch_service(monkeypatch, db)
    monkeypatch.setattr(
        service,
        "apply_grant",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("duplicate must not grant")),
    )

    result = service.purchase_item_with_stars(
        uid="buyer", item_id="test_item", stars_paid=100, charge_id="charge-recovery-1"
    )

    assert result["status"] == "DUPLICATE"
    assert len(db["revenue_ledger"]) == 1
    assert db["revenue_ledger"][0]["reference"] == "charge-recovery-1"
    assert db["star_item_orders"]["stars:charge-recovery-1"]["status"] == "FULFILLED"
