import unittest
from unittest.mock import patch

from core import bnb_deposit_service


class BnbDepositServiceTests(unittest.TestCase):
    @patch.object(bnb_deposit_service, "record_transaction")
    @patch.object(bnb_deposit_service, "verify_bnb_deposit")
    @patch.object(bnb_deposit_service, "get_binding")
    def test_settlement_requires_bound_sender(self, get_binding, verify, record):
        get_binding.return_value = {"uid": "u1", "address": "0xBound"}
        verify.return_value = {
            "ok": True,
            "from": "0xOther",
            "to": "0xTreasury",
            "amount_bnb": 1,
            "block": 100,
            "confirmations": 20,
        }
        with self.assertRaisesRegex(ValueError, "BNB_TX_SENDER_NOT_BOUND_WALLET"):
            bnb_deposit_service.settle_bnb_deposit("u1", "0xtx")
        record.assert_not_called()

    @patch.object(bnb_deposit_service, "record_transaction", return_value=1234)
    @patch.object(bnb_deposit_service, "verify_bnb_deposit")
    @patch.object(bnb_deposit_service, "get_binding")
    def test_settlement_credits_only_verified_sender(self, get_binding, verify, record):
        get_binding.return_value = {"uid": "u1", "address": "0xBound"}
        verify.return_value = {
            "ok": True,
            "from": "0xBOUND",
            "to": "0xTreasury",
            "amount_bnb": 2.5,
            "block": 100,
            "confirmations": 20,
        }
        result = bnb_deposit_service.settle_bnb_deposit("u1", "0xTX")
        self.assertEqual(result["credits"], 2500)
        self.assertEqual(result["balance_after"], 1234)
        record.assert_called_once()

    @patch.object(bnb_deposit_service, "record_transaction")
    @patch.object(bnb_deposit_service, "verify_bnb_deposit")
    @patch.object(bnb_deposit_service, "get_binding", return_value=None)
    def test_settlement_requires_wallet_binding(self, get_binding, verify, record):
        with self.assertRaisesRegex(ValueError, "BNB_WALLET_NOT_VERIFIED"):
            bnb_deposit_service.settle_bnb_deposit("u1", "0xtx")
        verify.assert_not_called()
        record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
