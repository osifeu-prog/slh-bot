"""Regression tests for deposits that do not increase the receiving Treasury.

A transfer from an address to itself must never be counted as a deposit or
produce internal Credits/SLH balance.
"""
from unittest.mock import Mock, patch

from core import deposit_monitor, slh_deposit_service


TX_HASH = "0x" + "ab" * 32
SELF = "0x1111111111111111111111111111111111111111"
TOKEN = "0x2222222222222222222222222222222222222222"


def _web3_stub(fake_w3):
    class StubWeb3:
        HTTPProvider = staticmethod(lambda _rpc: object())
        is_address = staticmethod(
            lambda value: isinstance(value, str)
            and len(value) == 42
            and value.startswith("0x")
        )
        to_checksum_address = staticmethod(lambda value: value)

        def __new__(cls, _provider):
            return fake_w3

    return StubWeb3


def test_bnb_verification_rejects_self_transfer_as_not_a_deposit():
    fake_w3 = Mock()
    fake_w3.eth.chain_id = 56
    fake_w3.eth.block_number = 200
    fake_w3.to_checksum_address = lambda value: value
    fake_w3.eth.get_transaction.return_value = {
        "from": SELF,
        "to": SELF,
        "value": 10**16,
    }
    fake_w3.eth.get_transaction_receipt.return_value = {
        "status": 1,
        "blockNumber": 100,
    }

    config = {
        "rpc": "https://rpc.invalid",
        "treasury_wallet": SELF,
        "confirmations": 15,
    }
    with patch("core.deposit_monitor.get_bsc_config", return_value=config), patch(
        "core.deposit_monitor.state_manager.load_db", return_value={}
    ), patch("core.deposit_monitor.Web3", _web3_stub(fake_w3)):
        result = deposit_monitor.verify_bnb_deposit(TX_HASH)

    assert result["ok"] is False
    assert result["error"] == "BNB_SELF_TRANSFER_NOT_DEPOSIT"


def test_slh_verification_rejects_self_transfer_as_not_a_deposit():
    topic = "0x" + ("0" * 24) + SELF[2:]
    fake_w3 = Mock()
    fake_w3.eth.block_number = 200
    fake_w3.eth.get_transaction_receipt.return_value = {
        "status": 1,
        "blockNumber": 100,
        "logs": [
            {
                "address": TOKEN,
                "topics": [slh_deposit_service.TRANSFER_TOPIC, topic, topic],
                "data": "0x" + format(10**15, "064x"),
                "logIndex": 1,
            }
        ],
    }

    config = {
        "rpc": "https://rpc.invalid",
        "treasury_wallet": SELF,
        "token_contract": TOKEN,
        "confirmations": 15,
    }
    with patch("core.slh_deposit_service.get_bsc_config", return_value=config), patch(
        "core.slh_deposit_service.state_manager.load_db", return_value={}
    ), patch(
        "core.slh_deposit_service.assert_supply_unchanged", return_value={"ok": True}
    ), patch("core.slh_deposit_service.Web3", _web3_stub(fake_w3)):
        result = slh_deposit_service.verify_slh_deposit(TX_HASH)

    assert result["ok"] is False
    assert result["error"] == "SLH_SELF_TRANSFER_NOT_DEPOSIT"
