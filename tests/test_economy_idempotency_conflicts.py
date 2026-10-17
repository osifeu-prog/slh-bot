from copy import deepcopy
from unittest.mock import patch

import pytest

from core import economy_service
from store import purchase_service


IDEMPOTENCY_KEY = "purchase:req-001:debit"


def _db():
    return {
        "users": {
            "buyer": {"wallet": {"credits": 90.0}},
            "other": {"wallet": {"credits": 100.0}},
        },
        "ledger": [
            {
                "time": "2026-10-17T10:00:00+00:00",
                "uid": "buyer",
                "before": 100.0,
                "amount": -10.0,
                "after": 90.0,
                "reason": "store:purchase",
                "meta": {
                    "idempotency_key": IDEMPOTENCY_KEY,
                    "purchase_id": "purchase:req-001",
                    "item_id": "old-item",
                },
            }
        ],
        "purchases": {},
        "products": {},
    }


def _atomic_update_for(db):
    return patch.object(
        economy_service.state_manager,
        "atomic_update",
        side_effect=lambda mutate: mutate(db),
    )


def test_conflicting_uid_with_same_idempotency_key_fails_closed():
    db = _db()
    before = deepcopy(db)

    with _atomic_update_for(db):
        with pytest.raises(ValueError, match="IDEMPOTENCY_KEY_CONFLICT"):
            economy_service.record_transaction(
                "other",
                -10.0,
                reason="store:purchase",
                meta={
                    "idempotency_key": IDEMPOTENCY_KEY,
                    "purchase_id": "purchase:req-001",
                    "item_id": "old-item",
                },
            )

    assert db == before


@pytest.mark.parametrize(
    ("uid", "amount", "reason", "item_id"),
    [
        ("buyer", -11.0, "store:purchase", "old-item"),
        ("buyer", -10.0, "store:refund", "old-item"),
        ("buyer", -10.0, "store:purchase", "different-item"),
    ],
)
def test_conflicting_amount_reason_or_item_fails_closed(uid, amount, reason, item_id):
    db = _db()
    before = deepcopy(db)

    with _atomic_update_for(db):
        with pytest.raises(ValueError, match="IDEMPOTENCY_KEY_CONFLICT"):
            economy_service.record_transaction(
                uid,
                amount,
                reason=reason,
                meta={
                    "idempotency_key": IDEMPOTENCY_KEY,
                    "purchase_id": "purchase:req-001",
                    "item_id": item_id,
                },
            )

    assert db == before


def test_exact_legacy_replay_is_a_noop_and_keeps_numeric_return_contract():
    db = _db()
    before = deepcopy(db)

    with _atomic_update_for(db):
        result = economy_service.record_transaction(
            "buyer",
            -10.0,
            reason="store:purchase",
            meta={
                "idempotency_key": IDEMPOTENCY_KEY,
                "purchase_id": "purchase:req-001",
                "item_id": "old-item",
            },
        )

    assert result == 90.0
    assert db == before


def test_details_api_reports_conflict_without_mutation():
    db = _db()
    before = deepcopy(db)

    with _atomic_update_for(db):
        result = economy_service.record_transaction(
            "other",
            -10.0,
            reason="store:purchase",
            meta={
                "idempotency_key": IDEMPOTENCY_KEY,
                "purchase_id": "purchase:req-001",
                "item_id": "old-item",
            },
            return_details=True,
        )

    assert result["status"] == "CONFLICT"
    assert result["credits_applied"] == 0.0
    assert db == before


def test_store_does_not_fulfill_purchase_after_idempotency_conflict():
    db = _db()
    before_balance = db["users"]["buyer"]["wallet"]["credits"]
    items = {
        "new-item": {
            "type": "digital",
            "name": "New item",
            "price": 10.0,
            "grant": {"digital": "new-item"},
        }
    }

    with (
        patch.object(purchase_service.state_manager, "load_db", return_value=db),
        _atomic_update_for(db),
        patch.object(purchase_service, "load_items", return_value=items),
        patch.object(purchase_service, "resolve_item_id", return_value="new-item"),
        patch.object(purchase_service, "apply_grant") as apply_grant,
    ):
        success, result = purchase_service.purchase(
            "buyer", "new-item", request_id="req-001"
        )

    assert success is False
    assert result == "PAYMENT_FAILED"
    assert db["users"]["buyer"]["wallet"]["credits"] == before_balance
    assert len(db["ledger"]) == 1
    assert db["purchases"]["purchase:req-001"]["status"] == "REJECTED"
    apply_grant.assert_not_called()


def test_replay_missing_existing_store_identity_metadata_fails_closed():
    db = _db()
    before = deepcopy(db)

    with _atomic_update_for(db):
        with pytest.raises(ValueError, match="IDEMPOTENCY_KEY_CONFLICT"):
            economy_service.record_transaction(
                "buyer",
                -10.0,
                reason="store:purchase",
                # Same key and amount is not sufficient: the original row
                # bound this debit to a specific purchase and item.
                meta={"idempotency_key": IDEMPOTENCY_KEY},
            )

    assert db == before
