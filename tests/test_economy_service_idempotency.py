"""Credits transaction idempotency conflicts must fail closed."""

import copy

from core import economy_service
from store import purchase_service


def _existing_entry(*, uid="buyer", amount=-20.0, reason="store:purchase", key="same-key", purchase_id="purchase:old", item_id="old-item"):
    return {
        "uid": uid,
        "before": 100.0,
        "amount": amount,
        "after": 100.0 + amount,
        "reason": reason,
        "meta": {
            "idempotency_key": key,
            "purchase_id": purchase_id,
            "item_id": item_id,
        },
    }


def _db(entry=None):
    return {
        "users": {
            "buyer": {"wallet": {"credits": 80.0}},
            "other": {"wallet": {"credits": 50.0}},
        },
        "ledger": [copy.deepcopy(entry)] if entry else [],
        "purchases": {},
        "products": {},
    }


def _record(monkeypatch, db, *, uid="buyer", amount=-20.0, reason="store:purchase", meta=None, return_details=False):
    monkeypatch.setattr(
        economy_service.state_manager,
        "atomic_update",
        lambda mutate: mutate(db),
    )
    return economy_service.record_transaction(
        uid=uid,
        amount=amount,
        reason=reason,
        meta=meta or {"idempotency_key": "same-key", "purchase_id": "purchase:old", "item_id": "old-item"},
        return_details=return_details,
    )


def test_conflicting_legacy_replays_return_false_without_mutation(monkeypatch):
    entry = _existing_entry()
    for kwargs in (
        {"uid": "other", "amount": -20.0, "reason": "store:purchase"},
        {"uid": "buyer", "amount": -21.0, "reason": "store:purchase"},
        {"uid": "buyer", "amount": -20.0, "reason": "store:other"},
    ):
        db = _db(entry)
        before = copy.deepcopy(db)
        meta = {
            "idempotency_key": "same-key",
            "purchase_id": "purchase:old",
            "item_id": "old-item",
        }

        result = _record(monkeypatch, db, meta=meta, **kwargs)

        assert result is False
        assert db == before


def test_conflicting_purchase_identity_returns_false_even_when_amount_matches(monkeypatch):
    db = _db(_existing_entry())
    before = copy.deepcopy(db)

    result = _record(
        monkeypatch,
        db,
        meta={
            "idempotency_key": "same-key",
            "purchase_id": "purchase:new",
            "item_id": "different-item",
        },
    )

    assert result is False
    assert db == before


def test_details_contract_reports_conflict_for_mismatched_identity(monkeypatch):
    db = _db(_existing_entry())
    before = copy.deepcopy(db)

    result = _record(
        monkeypatch,
        db,
        meta={
            "idempotency_key": "same-key",
            "purchase_id": "purchase:new",
            "item_id": "new-item",
        },
        return_details=True,
    )

    assert result["status"] == "CONFLICT"
    assert result["credits_applied"] == 0.0
    assert db == before


def test_exact_legacy_replay_preserves_return_contract_without_mutation(monkeypatch):
    db = _db(_existing_entry())
    before = copy.deepcopy(db)

    result = _record(
        monkeypatch,
        db,
        meta={
            "idempotency_key": "same-key",
            "purchase_id": "purchase:old",
            "item_id": "old-item",
        },
    )

    assert result == 80.0
    assert db == before


def test_exact_details_replay_is_duplicate_without_mutation(monkeypatch):
    db = _db(_existing_entry())
    before = copy.deepcopy(db)

    result = _record(
        monkeypatch,
        db,
        meta={
            "idempotency_key": "same-key",
            "purchase_id": "purchase:old",
            "item_id": "old-item",
        },
        return_details=True,
    )

    assert result["status"] == "DUPLICATE"
    assert result["credits_applied"] == 0.0
    assert result["existing_uid"] == "buyer"
    assert db == before


def test_store_purchase_does_not_fulfil_on_idempotency_conflict(monkeypatch):
    request_id = "conflicting-request"
    purchase_id = "purchase:" + request_id
    idempotency_key = purchase_id + ":debit"
    conflict_entry = _existing_entry(
        uid="other",
        amount=-10.0,
        key=idempotency_key,
        purchase_id="purchase:other",
        item_id="other-item",
    )
    db = {
        "users": {
            "buyer": {"wallet": {"credits": 100.0}},
            "other": {"wallet": {"credits": 90.0}},
        },
        "ledger": [copy.deepcopy(conflict_entry)],
        "purchases": {},
        "products": {},
    }
    ledger_before = copy.deepcopy(db["ledger"])
    catalog = {
        "digital-item": {
            "name": "Test digital item",
            "type": "digital",
            "price": 10.0,
            "grant": {"permission": "test-entitlement"},
        }
    }

    monkeypatch.setattr(purchase_service.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(
        purchase_service.state_manager,
        "atomic_update",
        lambda mutate: mutate(db),
    )
    monkeypatch.setattr(purchase_service, "load_items", lambda: catalog)
    monkeypatch.setattr(
        purchase_service,
        "resolve_item_id",
        lambda item_id, items: item_id if item_id in items else None,
    )
    monkeypatch.setattr(
        purchase_service,
        "apply_grant",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not fulfil")),
    )

    success, result = purchase_service.purchase(
        "buyer", "digital-item", request_id=request_id
    )

    assert success is False
    assert result == "PAYMENT_FAILED"
    assert db["users"]["buyer"]["wallet"]["credits"] == 100.0
    assert db["ledger"] == ledger_before
    assert db["purchases"][purchase_id]["status"] == "REJECTED"
