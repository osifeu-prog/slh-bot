from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from core import secondary_distribution_service as svc


OWNER = "1"
UID = "123"
WALLET = "0x1111111111111111111111111111111111111111"
RECIPIENT = "0x2222222222222222222222222222222222222222"
TOKEN = "0xACb0A09414CEA1C879c67bB7A877E4e19480f022"


def _db():
    return {
        "users": {UID: {"wallet": {}}},
        "secondary_distribution_wallets": {
            UID: {
                "uid": UID,
                "address": WALLET,
                "status": "active",
                "per_tx_limit_slh": "100",
                "daily_limit_slh": "250",
                "chain_id": 56,
            }
        },
        "secondary_distribution_pending": {},
        "secondary_distribution_wallet_audit": [],
    }


def _binding():
    return {"uid": UID, "chain": "bsc", "address": WALLET}


def test_requires_registered_wallet(monkeypatch):
    monkeypatch.setattr(svc, "get_binding", lambda uid: _binding())
    with patch.object(svc.state_manager, "load_db", return_value={}):
        with pytest.raises(ValueError, match="SECONDARY_DISTRIBUTION_WALLET_NOT_ACTIVE"):
            svc.prepare_secondary_slh_transfer(UID, RECIPIENT, "10", "r1")


def test_enforces_per_transaction_limit(monkeypatch):
    db = _db()
    monkeypatch.setattr(svc, "get_binding", lambda uid: _binding())
    with patch.object(svc.state_manager, "load_db", return_value=db):
        with pytest.raises(ValueError, match="PER_TX_LIMIT_EXCEEDED"):
            svc.prepare_secondary_slh_transfer(UID, RECIPIENT, "101", "r1")


def test_counts_pending_amount_against_daily_limit(monkeypatch):
    db = _db()
    now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(svc, "_now", lambda: now)
    db["secondary_distribution_pending"]["r0"] = {
        "request_id": "r0",
        "uid": UID,
        "status": "prepared",
        "amount_slh": "200",
        "prepared_at": (now - timedelta(minutes=5)).isoformat(),
        "expires_at": (now + timedelta(minutes=5)).isoformat(),
    }
    monkeypatch.setattr(svc, "get_binding", lambda uid: _binding())
    with patch.object(svc.state_manager, "load_db", return_value=db):
        with pytest.raises(ValueError, match="DAILY_LIMIT_EXCEEDED"):
            svc.prepare_secondary_slh_transfer(UID, RECIPIENT, "51", "r1")

def test_prepare_is_user_signed_only_and_returns_payload(monkeypatch):
    db = _db()
    monkeypatch.setattr(svc, "get_binding", lambda uid: _binding())
    class Fn:
        def __init__(self, value): self.value = value
        def call(self): return self.value
    class Contract:
        functions = type("Fns", (), {
            "decimals": lambda self: Fn(15),
            "balanceOf": lambda self, address: Fn(10**18),
        })()
    class Eth:
        chain_id = 56
        gas_price = 3
        block_number = 123
        def contract(self, **kwargs): return Contract()
        def estimate_gas(self, tx): return 21000
        def get_balance(self, address): return 10**18
    class W3:
        eth = Eth()
        def is_connected(self): return True
    monkeypatch.setattr(svc, "_client", lambda cfg: W3())
    monkeypatch.setattr(svc, "_bsc_config", lambda: {"rpc": "x", "token_contract": TOKEN})
    with patch.object(svc.state_manager, "load_db", return_value=db),          patch.object(svc.state_manager, "atomic_update", side_effect=lambda fn: fn(db)):
        result = svc.prepare_secondary_slh_transfer(UID, RECIPIENT, "10", "r1")
    assert result["status"] == "prepared"
    assert result["broadcast"] is False
    assert result["custody"] is False
    assert result["tx"]["from"].lower() == WALLET.lower()
    assert result["tx"]["to"].lower() == TOKEN.lower()
    assert db["secondary_distribution_pending"]["r1"]["amount_slh"] == "10"


def test_request_id_is_idempotent(monkeypatch):
    db = _db()
    db["secondary_distribution_pending"]["r1"] = {
        "request_id": "r1",
        "uid": UID,
        "status": "prepared",
        "amount_slh": "10",
        "prepared_at": "2026-10-02T23:00:00+00:00",
        "expires_at": "2099-10-02T23:10:00+00:00",
    }
    monkeypatch.setattr(svc, "get_binding", lambda uid: _binding())
    class Fn:
        def __init__(self, value): self.value = value
        def call(self): return self.value
    class Contract:
        functions = type("Fns", (), {
            "decimals": lambda self: Fn(15),
            "balanceOf": lambda self, address: Fn(10**18),
        })()
    class Eth:
        chain_id = 56
        gas_price = 3
        def contract(self, **kwargs): return Contract()
        def estimate_gas(self, tx): return 21000
        def get_balance(self, address): return 10**18
    class W3:
        eth = Eth()
        def is_connected(self): return True
    monkeypatch.setattr(svc, "_client", lambda cfg: W3())
    monkeypatch.setattr(svc, "_bsc_config", lambda: {"rpc": "x", "token_contract": TOKEN})
    with patch.object(svc.state_manager, "load_db", return_value=db):
        result = svc.prepare_secondary_slh_transfer(UID, RECIPIENT, "10", "r1")
    assert result["request_id"] == "r1"
    assert result["status"] == "prepared"
    assert result["tx"]["from"].lower() == WALLET.lower()
    assert result["tx"]["to"].lower() == TOKEN.lower()


def test_cancel_releases_pending_request(monkeypatch):
    db = _db()
    db["secondary_distribution_pending"]["r1"] = {
        "request_id": "r1", "uid": UID, "status": "prepared",
        "amount_slh": "10",
    }
    with patch.object(svc.state_manager, "atomic_update", side_effect=lambda fn: fn(db)):
        result = svc.cancel_secondary_slh_transfer(UID, "r1")
    assert result["status"] == "cancelled"
    assert db["secondary_distribution_pending"]["r1"]["status"] == "cancelled"


def test_unbounded_mode_does_not_block_large_amount(monkeypatch):
    db = _db()
    db["secondary_distribution_wallets"][UID]["limit_mode"] = "unbounded"
    monkeypatch.setattr(svc, "get_binding", lambda uid: _binding())
    class Fn:
        def __init__(self, value): self.value = value
        def call(self): return self.value
    class Contract:
        functions = type("Fns", (), {
            "decimals": lambda self: Fn(15),
            "balanceOf": lambda self, address: Fn(10**30),
        })()
    class Eth:
        chain_id = 56
        gas_price = 3
        def contract(self, **kwargs): return Contract()
        def estimate_gas(self, tx): return 21000
        def get_balance(self, address): return 10**18
    class W3:
        eth = Eth()
        def is_connected(self): return True
    monkeypatch.setattr(svc, "_client", lambda cfg: W3())
    monkeypatch.setattr(svc, "_bsc_config", lambda: {"rpc": "x", "token_contract": TOKEN})
    with patch.object(svc.state_manager, "load_db", return_value=db),          patch.object(svc.state_manager, "atomic_update", side_effect=lambda fn: fn(db)):
        result = svc.prepare_secondary_slh_transfer(UID, RECIPIENT, "1000000000", "large-1")
    assert result["status"] == "prepared"
    assert result["amount_slh"] == "1000000000"
    assert result["broadcast"] is False
    assert result["custody"] is False


def test_confirm_treats_missing_transaction_as_retryable(monkeypatch):
    db = _db()
    db["secondary_distribution_pending"]["r1"] = {
        "request_id": "r1",
        "uid": UID,
        "status": "prepared",
        "address": WALLET,
        "recipient": RECIPIENT,
        "token_contract": TOKEN,
        "amount_slh": "1",
        "amount_raw": 10**15,
        "prepared_at": "2026-10-06T15:00:00+00:00",
        "expires_at": "2099-10-06T15:10:00+00:00",
    }

    class Eth:
        def get_transaction_receipt(self, tx_hash):
            from web3.exceptions import TransactionNotFound
            raise TransactionNotFound(tx_hash)

    class W3:
        eth = Eth()

    monkeypatch.setattr(svc, "_client", lambda cfg: W3())
    monkeypatch.setattr(svc, "_bsc_config", lambda: {"rpc": "x", "confirmations": 15})
    with patch.object(svc.state_manager, "load_db", return_value=db):
        with pytest.raises(ValueError, match="TRANSACTION_NOT_FOUND_RETRYABLE"):
            svc.confirm_secondary_slh_transfer(UID, "r1", "0xabc")


def test_confirm_treats_transaction_lookup_race_as_retryable(monkeypatch):
    db = _db()
    db["secondary_distribution_pending"]["r1"] = {
        "request_id": "r1",
        "uid": UID,
        "status": "prepared",
        "address": WALLET,
        "recipient": RECIPIENT,
        "token_contract": TOKEN,
        "amount_slh": "1",
        "amount_raw": 10**15,
        "prepared_at": "2026-10-06T15:00:00+00:00",
        "expires_at": "2099-10-06T15:10:00+00:00",
    }

    class Eth:
        block_number = 114

        def get_transaction_receipt(self, tx_hash):
            return {"status": 1, "blockNumber": 100, "logs": []}

        def get_transaction(self, tx_hash):
            from web3.exceptions import TransactionNotFound
            raise TransactionNotFound(tx_hash)

    class W3:
        eth = Eth()

    monkeypatch.setattr(svc, "_client", lambda cfg: W3())
    monkeypatch.setattr(svc, "_bsc_config", lambda: {"rpc": "x", "confirmations": 15})
    with patch.object(svc.state_manager, "load_db", return_value=db):
        with pytest.raises(ValueError, match="TRANSACTION_NOT_FOUND_RETRYABLE"):
            svc.confirm_secondary_slh_transfer(UID, "r1", "0xabc")
