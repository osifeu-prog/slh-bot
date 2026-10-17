import copy
from unittest.mock import patch

import pytest

from core import secondary_distribution_service, slh_distribution


SENDER = "sender"
RECIPIENT_UID = "recipient"


def _p2p_db():
    return {
        "users": {
            SENDER: {"wallet": {"token_balance": 10.0, "live_token_balance": 10.0}},
            RECIPIENT_UID: {"wallet": {"token_balance": 0.0, "live_token_balance": 0.0}},
        },
        "slh_token_ledger": [],
    }


def test_p2p_slh_transfer_defaults_closed_without_state_change(monkeypatch):
    monkeypatch.delenv("SLH_P2P_TRANSFERS_OPEN", raising=False)
    db = _p2p_db()
    before = copy.deepcopy(db)
    with patch.object(
        slh_distribution.state_manager,
        "atomic_update",
        side_effect=lambda mutate: mutate(db),
    ):
        with pytest.raises(ValueError, match="SLH_P2P_TRANSFERS_CLOSED"):
            slh_distribution.transfer(
                sender_uid=SENDER,
                recipient_uid=RECIPIENT_UID,
                amount="1",
                event_id="p2p-test-1",
            )
    assert db == before


def test_p2p_slh_transfer_requires_exact_open_value(monkeypatch):
    monkeypatch.setenv("SLH_P2P_TRANSFERS_OPEN", "true")
    db = _p2p_db()
    with patch.object(
        slh_distribution.state_manager,
        "atomic_update",
        side_effect=lambda mutate: mutate(db),
    ):
        with pytest.raises(ValueError, match="SLH_P2P_TRANSFERS_CLOSED"):
            slh_distribution.transfer(
                sender_uid=SENDER,
                recipient_uid=RECIPIENT_UID,
                amount="1",
                event_id="p2p-test-2",
            )
    assert db["slh_token_ledger"] == []


def test_p2p_slh_transfer_can_be_enabled_explicitly(monkeypatch):
    monkeypatch.setenv("SLH_P2P_TRANSFERS_OPEN", "1")
    db = _p2p_db()
    with patch.object(
        slh_distribution.state_manager,
        "atomic_update",
        side_effect=lambda mutate: mutate(db),
    ):
        result = slh_distribution.transfer(
            sender_uid=SENDER,
            recipient_uid=RECIPIENT_UID,
            amount="2",
            event_id="p2p-test-3",
        )
    assert result["status"] == "completed"
    assert db["users"][SENDER]["wallet"]["token_balance"] == 8.0
    assert db["users"][RECIPIENT_UID]["wallet"]["token_balance"] == 2.0
    assert len(db["slh_token_ledger"]) == 1


def test_exact_p2p_replay_remains_noop_after_gate_closes_and_sender_freezes(monkeypatch):
    monkeypatch.setenv("SLH_P2P_TRANSFERS_OPEN", "1")
    db = _p2p_db()
    with patch.object(
        slh_distribution.state_manager,
        "atomic_update",
        side_effect=lambda mutate: mutate(db),
    ):
        first = slh_distribution.transfer(
            sender_uid=SENDER,
            recipient_uid=RECIPIENT_UID,
            amount="2",
            event_id="p2p-replay-1",
        )
    assert first["status"] == "completed"
    db["users"][SENDER]["frozen"] = True
    monkeypatch.setenv("SLH_P2P_TRANSFERS_OPEN", "0")
    before = copy.deepcopy(db)
    with patch.object(
        slh_distribution.state_manager,
        "atomic_update",
        side_effect=lambda mutate: mutate(db),
    ):
        replay = slh_distribution.transfer(
            sender_uid=SENDER,
            recipient_uid=RECIPIENT_UID,
            amount="2",
            event_id="p2p-replay-1",
        )
    assert replay["status"] == "already_completed"
    assert db == before


def test_secondary_distribution_prepare_defaults_closed_before_wallet_or_rpc_work(monkeypatch):
    monkeypatch.delenv("SLH_BSC_SECONDARY_DISTRIBUTION_OPEN", raising=False)
    monkeypatch.setattr(
        secondary_distribution_service,
        "get_binding",
        lambda uid: pytest.fail("wallet binding must not be loaded when gate is closed"),
    )
    with patch.object(
        secondary_distribution_service.state_manager,
        "load_db",
        side_effect=AssertionError("database must not be loaded when gate is closed"),
    ):
        with pytest.raises(ValueError, match="SECONDARY_DISTRIBUTION_CLOSED"):
            secondary_distribution_service.prepare_secondary_slh_transfer(
                "123",
                "0x2222222222222222222222222222222222222222",
                "1",
                "closed-request",
            )


def test_secondary_distribution_prepare_only_opens_for_exact_one(monkeypatch):
    monkeypatch.setenv("SLH_BSC_SECONDARY_DISTRIBUTION_OPEN", "yes")
    with pytest.raises(ValueError, match="SECONDARY_DISTRIBUTION_CLOSED"):
        secondary_distribution_service.prepare_secondary_slh_transfer(
            "123",
            "0x2222222222222222222222222222222222222222",
            "1",
            "closed-request",
        )
