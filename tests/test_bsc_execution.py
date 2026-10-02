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


def test_server_signing_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SLH_BSC_SERVER_SIGNING_ENABLED", raising=False)
    monkeypatch.delenv("SLH_BSC_SERVER_SIGNER_ADDRESS", raising=False)
    assert bsc_execution.server_signing_enabled() is False
    snap = bsc_execution.policy_snapshot()
    assert snap["server_signing"] is False
    assert snap["server_signer_configured"] is False
    assert snap["key_storage"] == "external_signer_only"


def test_server_signing_requires_explicit_signer_address(monkeypatch):
    monkeypatch.setenv("SLH_BSC_SERVER_SIGNING_ENABLED", "1")
    monkeypatch.delenv("SLH_BSC_SERVER_SIGNER_ADDRESS", raising=False)
    assert bsc_execution.server_signing_enabled() is True
    class DummySigner:
        def address(self):
            return "0x1111111111111111111111111111111111111111"
        def sign_transaction(self, transaction):
            raise AssertionError("must not sign when signer gate is incomplete")
    with pytest.raises(ValueError, match="BSC_SERVER_SIGNER_NOT_CONFIGURED_OR_MISMATCH"):
        bsc_execution.execute_with_external_signer(
            {"chainId": 97},
            DummySigner(),
            expected_sender="0x1111111111111111111111111111111111111111",
        )


def test_broadcast_requires_execution_gate(monkeypatch):
    monkeypatch.delenv("SLH_BSC_EXECUTION_ENABLED", raising=False)
    with pytest.raises(ValueError, match="BSC_EXECUTION_DISABLED"):
        bsc_execution.broadcast_signed_transaction("0x01")

def test_broadcast_is_separately_gated(monkeypatch):
    monkeypatch.setenv("SLH_BSC_EXECUTION_ENABLED", "1")
    monkeypatch.setenv("SLH_BSC_EXECUTION_NETWORK", "bsc-testnet")
    monkeypatch.delenv("SLH_BSC_BROADCAST_ENABLED", raising=False)
    assert bsc_execution.broadcast_enabled() is False
    with pytest.raises(ValueError, match="BSC_BROADCAST_DISABLED"):
        bsc_execution.broadcast_signed_transaction("0x01")


def test_policy_reports_broadcast_gate(monkeypatch):
    monkeypatch.delenv("SLH_BSC_BROADCAST_ENABLED", raising=False)
    snap = bsc_execution.policy_snapshot()
    assert snap["broadcast"] is False
    assert snap["broadcast_gate"] == "SLH_BSC_BROADCAST_ENABLED"
