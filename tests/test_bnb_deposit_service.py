import unittest
from unittest.mock import patch

from core import bnb_deposit_service


class BnbDepositServiceTests(unittest.TestCase):
    def setUp(self):
        # Settlement tests isolate the production gate; live BNB remains closed.
        gate = patch(
            "core.bnb_deposit_service.bnb_deposits_open",
            return_value=True,
        )
        gate.start()
        self.addCleanup(gate.stop)

    @patch.object(bnb_deposit_service, "record_transaction")
    @patch.object(bnb_deposit_service, "verify_bnb_deposit")
    @patch.object(bnb_deposit_service, "get_binding")
    def test_settlement_requires_bound_sender(self, get_binding, verify, record):
        get_binding.return_value = {"uid": "u1", "address": "0xBound"}
        verify.return_value = {"ok": True, "from": "0xOther", "to": "0xTreasury", "amount_bnb": 1}
        with self.assertRaisesRegex(ValueError, "BNB_TX_SENDER_NOT_BOUND_WALLET"):
            bnb_deposit_service.settle_bnb_deposit("u1", "0xtx")
        record.assert_not_called()

    @patch.object(bnb_deposit_service, "record_transaction", return_value=1234)
    @patch.object(bnb_deposit_service, "verify_bnb_deposit")
    @patch.object(bnb_deposit_service, "get_binding")
    @patch.object(bnb_deposit_service.state_manager, "load_db")
    def test_settlement_credits_only_verified_sender(self, load_db, get_binding, verify, record):
        get_binding.return_value = {"uid": "u1", "address": "0xBound"}
        verify.return_value = {"ok": True, "from": "0xBOUND", "to": "0xTreasury", "amount_bnb": 2.5, "amount_wei": 2500000000000000000}
        load_db.return_value = {"ledger": []}
        result = bnb_deposit_service.settle_bnb_deposit("u1", "0xTX")
        self.assertEqual(result["credits"], 2500)
        self.assertEqual(result["balance_after"], 1234)
        self.assertFalse(result["idempotent"])
        record.assert_called_once()

    @patch.object(bnb_deposit_service, "record_transaction", return_value=1234)
    @patch.object(bnb_deposit_service, "verify_bnb_deposit")
    @patch.object(bnb_deposit_service, "get_binding")
    @patch.object(bnb_deposit_service.state_manager, "load_db")
    def test_replayed_transaction_is_detected_from_canonical_ledger(self, load_db, get_binding, verify, record):
        get_binding.return_value = {"uid": "u1", "address": "0xBound"}
        verify.return_value = {"ok": True, "from": "0xBound", "to": "0xTreasury", "amount_bnb": 2.5, "amount_wei": 2500000000000000000}
        entry = {"meta": {"idempotency_key": "bnb:deposit:0xtx"}}
        load_db.return_value = {"ledger": [entry]}
        result = bnb_deposit_service.settle_bnb_deposit("u1", "0xTX")
        self.assertTrue(result["idempotent"])
        self.assertEqual(result["balance_after"], 1234)

    @patch.object(bnb_deposit_service, "record_transaction", return_value=1234)
    @patch.object(bnb_deposit_service, "verify_bnb_deposit")
    @patch.object(bnb_deposit_service, "get_binding")
    @patch.object(bnb_deposit_service.state_manager, "load_db")
    def test_settlement_derives_credits_from_exact_wei(self, load_db, get_binding, verify, record):
        get_binding.return_value = {"uid": "u1", "address": "0xBound"}
        # 0.123456789012345678 BNB = 123.456789012345678 Credits.
        verify.return_value = {
            "ok": True,
            "from": "0xBOUND",
            "to": "0xTreasury",
            "amount_bnb": 0.12345678901234568,
            "amount_wei": 123456789012345678,
        }
        load_db.return_value = {"ledger": []}
        result = bnb_deposit_service.settle_bnb_deposit("u1", "0xTX")
        self.assertEqual(result["amount_wei"], 123456789012345678)
        self.assertEqual(result["credits"], 123.45678901234568)
        self.assertEqual(
            record.call_args.kwargs["meta"]["bnb_amount_wei"],
            123456789012345678,
        )

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
