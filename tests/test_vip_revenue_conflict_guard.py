"""VIP Stars subscription replay conflicts fail before benefit/state mutation."""

import copy

from core import stars_payment_authority as authority


def _atomic_memory_db(monkeypatch, db):
    monkeypatch.setattr(
        authority.state_manager,
        "atomic_update",
        lambda mutate: mutate(db),
    )


def test_existing_vip_charge_with_different_uid_is_conflict_and_read_only(monkeypatch):
    db = {
        "users": {
            "100": {"wallet": {"credits": 0}, "permissions": ["vip_access"], "vip_access_until": 9000},
            "200": {"wallet": {"credits": 0}, "permissions": ["vip_access"], "vip_access_until": 9000},
        },
        "vip_subscriptions": {
            "charge-vip-1": {
                "charge_id": "charge-vip-1",
                "uid": "100",
                "stars_paid": 499,
                "started_at": 1000,
                "expires_at": 1000 + 2592000,
                "status": "ACTIVE",
                "launch_offer_qualified": False,
                "fulfillment_status": "completed",
            }
        },
    }
    before = copy.deepcopy(db)
    _atomic_memory_db(monkeypatch, db)
    monkeypatch.setattr(
        authority,
        "apply_vip_benefits",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("conflict must not fulfill")),
    )

    result = authority.record_vip_subscription_payment(
        uid="200", stars_paid=499, charge_id="charge-vip-1", now=5000
    )

    assert result["status"] == "conflict"
    assert "uid" in result["conflicting_fields"]
    assert db == before


def test_conflicting_revenue_uid_blocks_new_vip_subscription_without_mutation(monkeypatch):
    db = {
        "users": {"100": {"wallet": {"credits": 0}, "permissions": []}},
        "revenue_ledger": [
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "source": "telegram_stars_subscription",
                "amount": 499.0,
                "currency": "XTR",
                "reference": "charge-vip-2",
                "uid": "200",
                "meta": {"kind": "vip_monthly"},
            }
        ],
    }
    before = copy.deepcopy(db)
    _atomic_memory_db(monkeypatch, db)
    monkeypatch.setattr(
        authority,
        "apply_vip_benefits",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("conflict must not fulfill")),
    )

    result = authority.record_vip_subscription_payment(
        uid="100", stars_paid=499, charge_id="charge-vip-2", now=5000
    )

    assert result["status"] == "conflict"
    assert "revenue.uid" in result["conflicting_fields"]
    assert db == before


def test_exact_completed_vip_replay_recovers_missing_revenue_without_extending_or_fulfilling(monkeypatch):
    db = {
        "users": {
            "100": {
                "wallet": {"credits": 0},
                "permissions": ["vip_access"],
                "vip_access_until": 9000,
            }
        },
        "vip_subscriptions": {
            "charge-vip-3": {
                "charge_id": "charge-vip-3",
                "uid": "100",
                "stars_paid": 499,
                "started_at": 1000,
                "expires_at": 9000,
                "status": "ACTIVE",
                "launch_offer_qualified": False,
                "fulfillment_status": "completed",
            }
        },
    }
    before_until = db["users"]["100"]["vip_access_until"]
    _atomic_memory_db(monkeypatch, db)
    monkeypatch.setattr(
        authority,
        "apply_vip_benefits",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("completed replay must not fulfill")),
    )

    result = authority.record_vip_subscription_payment(
        uid="100", stars_paid=499, charge_id="charge-vip-3", now=5000
    )

    assert result["status"] == "duplicate"
    assert db["users"]["100"]["vip_access_until"] == before_until
    assert len(db["revenue_ledger"]) == 1
    assert db["revenue_ledger"][0]["reference"] == "charge-vip-3"
    assert db["vip_subscriptions"]["charge-vip-3"]["fulfillment_status"] == "completed"
