import time

import pytest
from eth_abi import decode

from core import bsc_swap


class FakeEth:
    block_number = 123

    def __init__(self, returns, balance=10**21):
        self.returns = list(returns)
        self.gas_price = 3_000_000_000
        self.balance = balance

    def call(self, _tx):
        return self.returns.pop(0)

    def get_balance(self, _address):
        return self.balance

    def estimate_gas(self, _tx):
        return 100_000


class FakeWeb3:
    def __init__(self, returns):
        self.eth = FakeEth(returns)


def hx(raw: int) -> bytes:
    return raw.to_bytes(max(32, (raw.bit_length() + 7) // 8), "big")


def addr_data(address: str) -> bytes:
    return bytes.fromhex(address[2:].lower().zfill(64))


def test_default_policy_is_disabled(monkeypatch):
    monkeypatch.delenv("SLH_BSC_EXECUTION_ENABLED", raising=False)
    monkeypatch.setenv("SLH_BSC_EXECUTION_NETWORK", "bsc-testnet")
    monkeypatch.delenv("SLH_BSC_USDT_TESTNET_ADDRESS", raising=False)
    assert bsc_swap.execution_enabled() is False
    assert bsc_swap.policy_snapshot()["chain_id"] == 97
    assert bsc_swap.policy_snapshot()["broadcast"] is False


def test_mainnet_stays_blocked_without_explicit_allow(monkeypatch):
    monkeypatch.setenv("SLH_BSC_EXECUTION_NETWORK", "bsc-mainnet")
    monkeypatch.delenv("SLH_BSC_EXECUTION_ALLOW_MAINNET", raising=False)
    with pytest.raises(ValueError, match="BSC_MAINNET_EXECUTION_DISABLED"):
        bsc_swap.policy_snapshot()


def test_amount_out_min_is_floor_exact():
    assert bsc_swap._amount_out_min(1000, 50) == 995
    assert bsc_swap._amount_out_min(999, 1) == 998


def test_invalid_slippage_rejected():
    with pytest.raises(ValueError, match="INVALID_SLIPPAGE_BPS"):
        bsc_swap._amount_out_min(1000, 1001)


def test_bnb_to_usdt_calldata_round_trips():
    sender = "0x1111111111111111111111111111111111111111"
    token = "0x2222222222222222222222222222222222222222"
    data = bsc_swap._encode_swap_exact_eth_for_tokens(
        990, [token, sender], sender, 123456
    )
    assert data.startswith("0x7ff36ab5")
    raw = bytes.fromhex(data[10:])
    decoded = decode(["uint256", "address[]", "address", "uint256"], raw)
    assert decoded[0] == 990
    assert list(decoded[1]) == [token, sender]
    assert decoded[2] == sender
    assert decoded[3] == 123456


def test_usdt_to_bnb_calldata_round_trips():
    sender = "0x1111111111111111111111111111111111111111"
    token = "0x2222222222222222222222222222222222222222"
    data = bsc_swap._encode_swap_exact_tokens_for_eth(
        1000, 900, [token, sender], sender, 654321
    )
    assert data.startswith("0x18cbafe5")
    raw = bytes.fromhex(data[10:])
    decoded = decode(["uint256", "uint256", "address[]", "address", "uint256"], raw)
    assert decoded[0] == 1000
    assert decoded[1] == 900
    assert list(decoded[2]) == [token, sender]
    assert decoded[3] == sender
    assert decoded[4] == 654321


def test_approval_is_exact_amount():
    token = "0x2222222222222222222222222222222222222222"
    data = bsc_swap._encode_approve(token, 12345)
    assert data.startswith("0x095ea7b3")
    raw = bytes.fromhex(data[10:])
    decoded = decode(["address", "uint256"], raw)
    assert decoded[0] == token
    assert decoded[1] == 12345



def test_uint256_rpc_bytes_decode_is_big_endian():
    raw = (123456789).to_bytes(32, "big")
    assert bsc_swap._decode_uint256(raw) == 123456789
