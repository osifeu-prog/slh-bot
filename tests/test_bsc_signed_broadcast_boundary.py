import os
import unittest
from unittest.mock import patch, Mock

from eth_account import Account
from web3 import Web3

from core import bsc_execution


class BSCSignedBroadcastBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.account = Account.create()
        self.other = Account.create()
        self.cfg = {
            "name": "bsc-testnet",
            "chain_id": 97,
            "rpc_url": "https://example.invalid",
            "native_symbol": "tBNB",
            "usdt_address": None,
        }
        self.web3 = Mock()

    def _env(self, **overrides):
        values = {
            "SLH_BSC_EXECUTION_ENABLED": "1",
            "SLH_BSC_EXECUTION_NETWORK": "bsc-testnet",
            "SLH_BSC_BROADCAST_ENABLED": "1",
            "SLH_BSC_EXECUTION_ALLOW_MAINNET": "0",
        }
        values.update(overrides)
        return patch.dict(os.environ, values, clear=False)

    def test_broadcast_is_fail_closed_without_broadcast_gate(self):
        with self._env(SLH_BSC_BROADCAST_ENABLED="0"):
            with self.assertRaisesRegex(ValueError, "BSC_BROADCAST_DISABLED"):
                bsc_execution.broadcast_signed_transaction(
                    "0x01",
                    expected_sender=self.account.address,
                )

    def test_wrong_bound_sender_is_rejected_before_broadcast(self):
        self.web3.eth.send_raw_transaction = Mock()
        with self._env():
            with patch.object(bsc_execution, "_client", return_value=self.web3),                  patch.object(bsc_execution, "recover_signed_sender", return_value=self.account.address):
                with self.assertRaisesRegex(ValueError, "SIGNED_TX_SENDER_MISMATCH"):
                    bsc_execution.broadcast_signed_transaction(
                        "0x01",
                        expected_sender=self.other.address,
                    )
        self.web3.eth.send_raw_transaction.assert_not_called()

    def test_already_known_transaction_is_idempotent(self):
        self.web3.eth.get_transaction.return_value = {"hash": "0xknown"}
        self.web3.eth.send_raw_transaction = Mock()
        with self._env():
            with patch.object(bsc_execution, "_client", return_value=self.web3),                  patch.object(bsc_execution, "recover_signed_sender", return_value=self.account.address):
                result = bsc_execution.broadcast_signed_transaction(
                    "0x01",
                    expected_sender=self.account.address,
                )
        self.assertTrue(result["ok"])
        self.assertTrue(result["already_broadcast"])
        self.assertTrue(result["custody"] is False)
        self.web3.eth.send_raw_transaction.assert_not_called()

    def test_new_signed_transaction_can_broadcast_when_explicitly_enabled(self):
        self.web3.eth.get_transaction.side_effect = Exception("not found")
        self.web3.eth.send_raw_transaction.return_value = b"\x12" * 32
        with self._env():
            with patch.object(bsc_execution, "_client", return_value=self.web3),                  patch.object(bsc_execution, "recover_signed_sender", return_value=self.account.address):
                result = bsc_execution.broadcast_signed_transaction(
                    "0x01",
                    expected_sender=self.account.address,
                )
        self.assertTrue(result["ok"])
        self.assertFalse(result["already_broadcast"])
        self.assertEqual(result["from"], self.account.address)
        self.assertTrue(result["custody"] is False)

    def test_receipt_is_scoped_to_bound_sender(self):
        receipt = {"status": 1, "blockNumber": 123, "gasUsed": 21000}
        self.web3.eth.get_transaction_receipt.return_value = receipt
        self.web3.eth.get_transaction.return_value = {"from": self.account.address}
        with self._env():
            with patch.object(bsc_execution, "_network", return_value=self.cfg),                  patch.object(bsc_execution, "_client", return_value=self.web3):
                result = bsc_execution.receipt_status(
                    "0x" + "11" * 32,
                    expected_sender=self.account.address,
                )
        self.assertTrue(result["succeeded"])

    def test_receipt_rejects_different_sender(self):
        self.web3.eth.get_transaction_receipt.return_value = {"status": 1}
        self.web3.eth.get_transaction.return_value = {"from": self.other.address}
        with self._env():
            with patch.object(bsc_execution, "_network", return_value=self.cfg),                  patch.object(bsc_execution, "_client", return_value=self.web3):
                with self.assertRaisesRegex(ValueError, "RECEIPT_SENDER_MISMATCH"):
                    bsc_execution.receipt_status(
                        "0x" + "22" * 32,
                        expected_sender=self.account.address,
                    )


if __name__ == "__main__":
    unittest.main()
