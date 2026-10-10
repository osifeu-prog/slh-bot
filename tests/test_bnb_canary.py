import os
import unittest
from unittest.mock import patch

from core import bnb_deposit_service as service


class BNBCanaryTests(unittest.TestCase):
    def test_owner_canary_allowed_when_global_gate_closed(self):
        with patch.dict(os.environ, {"BNB_DEPOSITS_OPEN": "0", "BNB_DEPOSITS_CANARY_UID": "8789977826"}, clear=False),              patch.object(service, "bnb_deposits_open", return_value=False),              patch.object(service, "bnb_readiness", return_value={"ready": True}),              patch.object(service, "get_binding", return_value={"address": "0xabc"}),              patch.object(service, "verify_bnb_deposit", return_value={
                 "ok": True,
                 "from": "0xabc",
                 "to": "0xtreasury",
                 "amount_wei": 10**15,
                 "amount_bnb": 0.001,
                 "block": 123,
                 "confirmations": 15,
             }),              patch.object(service.state_manager, "load_db", return_value={"ledger": [], "users": {"8789977826": {"wallet": {"credits": 7.19}}}}),              patch.object(service, "record_transaction", return_value={"status": "APPLIED", "balance_after": 8.19}):
            result = service.settle_bnb_deposit("8789977826", "0xTX")

        self.assertTrue(result["ok"])
        self.assertFalse(result["idempotent"])
        self.assertEqual(result["credits"], 1.0)

    def test_non_canary_user_stays_closed(self):
        with patch.dict(os.environ, {"BNB_DEPOSITS_OPEN": "0", "BNB_DEPOSITS_CANARY_UID": "8789977826"}, clear=False),              patch.object(service, "bnb_deposits_open", return_value=False),              patch.object(service, "bnb_readiness", return_value={"ready": True}):
            with self.assertRaisesRegex(ValueError, "BNB_DEPOSITS_CLOSED"):
                service.settle_bnb_deposit("123456789", "0xTX")

    def test_replay_reports_duplicate_from_atomic_credit_mutation(self):
        with patch.object(service, "bnb_deposits_open", return_value=True),              patch.object(service, "get_binding", return_value={"address": "0xabc"}),              patch.object(service, "verify_bnb_deposit", return_value={
                 "ok": True,
                 "from": "0xabc",
                 "to": "0xtreasury",
                 "amount_wei": 10**15,
                 "amount_bnb": 0.001,
                 "block": 123,
                 "confirmations": 15,
             }),              patch.object(service, "record_transaction", return_value={
                 "status": "DUPLICATE",
                 "balance_after": 8.19,
                 "credits_applied": 0.0,
             }) as record:
            result = service.settle_bnb_deposit("8789977826", "0xTX")

        self.assertTrue(result["idempotent"])
        self.assertEqual(result["settlement_status"], "DUPLICATE")
        self.assertEqual(result["credits"], 0.0)
        self.assertEqual(result["balance_after"], 8.19)
        record.assert_called_once()


if __name__ == "__main__":
    unittest.main()
