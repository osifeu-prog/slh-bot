from unittest.mock import patch

import pytest

from core import distribution_wallet_registry as registry


def _db(binding_address="0x1111111111111111111111111111111111111111"):
    return {
        "users": {"123": {"wallet": {}}},
        "wallet_bindings": {
            binding_address.lower(): {
                "uid": "123",
                "chain": "bsc",
                "address": binding_address,
                "verified_at": "2026-10-02T00:00:00+00:00",
            }
        },
        "bsc_settings": {
            "token_contract": "0xACb0A09414CEA1C879c67bB7A877E4e19480f022",
        },
    }


def test_requires_owner(monkeypatch):
    monkeypatch.setattr(registry, "get_binding", lambda uid: None)
    with pytest.raises(PermissionError, match="OWNER_ONLY"):
        registry.set_secondary_distribution_wallet(
            "999",
            "123",
            per_tx_limit="100",
            daily_limit="1000",
        )


def test_requires_verified_binding(monkeypatch):
    monkeypatch.setattr(registry, "is_owner", lambda uid: True)
    monkeypatch.setattr(registry, "get_binding", lambda uid: None)
    with pytest.raises(ValueError, match="BNB_WALLET_NOT_VERIFIED"):
        registry.set_secondary_distribution_wallet(
            "1",
            "123",
            per_tx_limit="100",
            daily_limit="1000",
        )


def test_daily_limit_must_cover_per_tx(monkeypatch):
    monkeypatch.setattr(registry, "is_owner", lambda uid: True)
    monkeypatch.setattr(
        registry,
        "get_binding",
        lambda uid: {
            "uid": "123",
            "chain": "bsc",
            "address": "0x1111111111111111111111111111111111111111",
        },
    )
    with pytest.raises(ValueError, match="DAILY_LIMIT_BELOW_PER_TX_LIMIT"):
        registry.set_secondary_distribution_wallet(
            "1",
            "123",
            per_tx_limit="1000",
            daily_limit="999",
        )


def test_registration_is_user_signed_only_and_does_not_move_funds(monkeypatch):
    db = _db()

    monkeypatch.setattr(registry, "is_owner", lambda uid: True)
    monkeypatch.setattr(registry, "get_binding", lambda uid: db["wallet_bindings"].copy().popitem()[1])

    with patch("core.distribution_wallet_registry.state_manager.load_db", return_value=db),          patch("core.distribution_wallet_registry.state_manager.atomic_update", side_effect=lambda fn: fn(db)):
        result = registry.set_secondary_distribution_wallet(
            "1",
            "123",
            per_tx_limit="100",
            daily_limit="500",
        )

    assert result["status"] == "active"
    assert result["mode"] == "user_signed_only"
    assert result["chain_id"] == 56
    assert result["asset"] == "SLH"
    assert result["binding_verified"] is True
    assert result["per_tx_limit_slh"] == "100"
    assert result["daily_limit_slh"] == "500"
    assert db["users"]["123"]["wallet"] == {}
    assert db["secondary_distribution_wallet_audit"][-1]["funds_moved"] is False
    assert db["secondary_distribution_wallet_audit"][-1]["custody_granted"] is False


def test_cannot_register_same_address_for_two_active_users(monkeypatch):
    db = _db()
    db["wallet_bindings"]["0x2222222222222222222222222222222222222222"] = {
        "uid": "456",
        "chain": "bsc",
        "address": "0x2222222222222222222222222222222222222222",
    }
    db["users"]["456"] = {"wallet": {}}
    db["secondary_distribution_wallets"] = {
        "123": {
            "uid": "123",
            "address": "0x1111111111111111111111111111111111111111",
            "status": "active",
        }
    }

    monkeypatch.setattr(registry, "is_owner", lambda uid: True)
    monkeypatch.setattr(
        registry,
        "get_binding",
        lambda uid: {
            "uid": "456",
            "chain": "bsc",
            "address": "0x1111111111111111111111111111111111111111",
        },
    )

    with patch("core.distribution_wallet_registry.state_manager.load_db", return_value=db),          patch("core.distribution_wallet_registry.state_manager.atomic_update", side_effect=lambda fn: fn(db)):
        with pytest.raises(ValueError, match="WALLET_ALREADY_REGISTERED_AS_SECONDARY"):
            registry.set_secondary_distribution_wallet(
                "1",
                "456",
                per_tx_limit="100",
                daily_limit="500",
            )


def test_revoke_keeps_audit_history(monkeypatch):
    db = _db()
    db["secondary_distribution_wallets"] = {
        "123": {
            "uid": "123",
            "address": "0x1111111111111111111111111111111111111111",
            "status": "active",
        }
    }

    monkeypatch.setattr(registry, "is_owner", lambda uid: True)

    with patch("core.distribution_wallet_registry.state_manager.load_db", return_value=db),          patch("core.distribution_wallet_registry.state_manager.atomic_update", side_effect=lambda fn: fn(db)):
        result = registry.revoke_secondary_distribution_wallet("1", "123")

    assert result["status"] == "revoked"
    assert db["secondary_distribution_wallet_audit"][-1]["event"] == "secondary_distribution_wallet_revoked"
    assert db["secondary_distribution_wallet_audit"][-1]["funds_moved"] is False
