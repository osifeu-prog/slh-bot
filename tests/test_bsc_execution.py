from decimal import Decimal

import pytest

from core import bsc_execution


def test_network_defaults_to_testnet(monkeypatch):
    monkeypatch.delenv("SLH_BSC_EXECUTION_NETWORK", raising=False)
    monkeypatch.delenv("SLH_BSC_EXECUTION_ALLOW_MAINNET", raising=False)
    cfg = bsc_execution._network()
    assert cfg["name"] == "bsc-testnet"
    assert cfg["chain_id"] == 97
    assert cfg["native_symbol"] == "tBNB"


def test_mainnet_requires_explicit_allow(monkeypatch):
    monkeypatch.setenv("SLH_BSC_EXECUTION_NETWORK", "bsc-mainnet")
    monkeypatch.setenv("SLH_BSC_EXECUTION_ALLOW_MAINNET", "0")
    with pytest.raises(ValueError, match="BSC_MAINNET_EXECUTION_DISABLED"):
        bsc_execution._network()


def test_execution_is_closed_by_default(monkeypatch):
    monkeypatch.delenv("SLH_BSC_EXECUTION_ENABLED", raising=False)
    assert bsc_execution.execution_enabled() is False


def test_parse_units_exact_and_rejects_extra_precision():
    assert bsc_execution._parse_units("1", 18) == 10**18
    assert bsc_execution._parse_units("0.0000001", 18) == 100_000_000_000
    with pytest.raises(ValueError, match="TOO_MANY_DECIMALS"):
        bsc_execution._parse_units("1.000001", 5)


def test_encode_erc20_transfer_is_canonical():
    recipient = "0x1111111111111111111111111111111111111111"
    data = bsc_execution._encode_erc20_transfer(recipient, 123456)
    assert data.startswith("0xa9059cbb")
    assert data == (
        "0xa9059cbb"
        "0000000000000000000000001111111111111111111111111111111111111111"
        "000000000000000000000000000000000000000000000000000000000001e240"
    )


def test_zero_and_bad_addresses_rejected():
    with pytest.raises(ValueError, match="INVALID_RECIPIENT_ADDRESS"):
        bsc_execution._checksum_address(bsc_execution.ZERO_ADDRESS, field="recipient")
    with pytest.raises(ValueError, match="INVALID_RECIPIENT_ADDRESS"):
        bsc_execution._checksum_address("nope", field="recipient")


def test_policy_never_broadcasts(monkeypatch):
    monkeypatch.delenv("SLH_BSC_EXECUTION_ENABLED", raising=False)
    monkeypatch.delenv("SLH_BSC_EXECUTION_NETWORK", raising=False)
    snap = bsc_execution.policy_snapshot()
    assert snap["enabled"] is False
    assert snap["chain_id"] == 97
    assert snap["broadcast"] is False
    assert snap["custody"] is False



from unittest.mock import patch

from eth_account import Account
from hexbytes import HexBytes


TEST_KEY = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


class _FakeEth:
    def __init__(self, tx_hash):
        self.chain_id = 56
        self._tx_hash = tx_hash

    def send_raw_transaction(self, raw):
        assert isinstance(raw, bytes)
        return self._tx_hash


class _FakeWeb3:
    def __init__(self, tx_hash):
        self.eth = _FakeEth(tx_hash)


def _signed_transaction(account):
    signed = account.sign_transaction(
        {
            "chainId": 56,
            "nonce": 0,
            "to": "0x1111111111111111111111111111111111111111",
            "value": 1,
            "gas": 21000,
            "gasPrice": 1_000_000_000,
        }
    )
    return signed.raw_transaction


def _mainnet_cfg():
    return {
        "name": "bsc-mainnet",
        "chain_id": 56,
        "rpc_url": "https://example.invalid",
        "native_symbol": "BNB",
        "usdt_address": None,
    }


def test_broadcast_signed_transaction_accepts_only_bound_wallet():
    account = Account.from_key(TEST_KEY)
    raw = _signed_transaction(account)
    tx_hash = HexBytes("0x" + "12" * 32)

    with patch("core.bsc_execution._require_enabled", return_value=_mainnet_cfg()),          patch("core.bsc_execution._client", return_value=_FakeWeb3(tx_hash)),          patch("core.bsc_execution._bound_account", return_value=account.address):
        result = bsc_execution.broadcast_signed_transaction("8789977826", raw)

    assert result["ok"] is True
    assert result["chain_id"] == 56
    assert result["tx_hash"] == tx_hash.hex()
    assert result["broadcast"] is True
    assert result["custody"] is False


def test_broadcast_signed_transaction_rejects_unbound_wallet():
    signer = Account.from_key(TEST_KEY)
    other = Account.create()
    raw = _signed_transaction(signer)
    tx_hash = HexBytes("0x" + "34" * 32)

    with patch("core.bsc_execution._require_enabled", return_value=_mainnet_cfg()),          patch("core.bsc_execution._client", return_value=_FakeWeb3(tx_hash)),          patch("core.bsc_execution._bound_account", return_value=other.address):
        with pytest.raises(ValueError, match="SIGNED_TX_SENDER_NOT_BOUND_WALLET"):
            bsc_execution.broadcast_signed_transaction("8789977826", raw)


def test_broadcast_signed_transaction_rejects_invalid_raw_transaction():
    with patch("core.bsc_execution._require_enabled", return_value=_mainnet_cfg()),          patch("core.bsc_execution._client", return_value=_FakeWeb3(HexBytes("0x" + "56" * 32))),          patch("core.bsc_execution._bound_account", return_value=Account.from_key(TEST_KEY).address):
        with pytest.raises(ValueError, match="INVALID_SIGNED_TRANSACTION"):
            bsc_execution.broadcast_signed_transaction("8789977826", "not-a-transaction")
