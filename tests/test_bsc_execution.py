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
