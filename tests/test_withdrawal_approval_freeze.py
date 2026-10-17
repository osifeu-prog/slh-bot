import copy
import os
import unittest
from unittest.mock import patch

from handlers import withdraw_request_handler as service


UID = "12345"
ADMIN_UID = "99999"
ADDRESS = "0:" + "33" * 32


class WithdrawalApprovalFreezeTests(unittest.TestCase):
    def setUp(self):
        self.db = {
            "users": {
                UID: {
                    "frozen": False,
                    "wallet": {"credits": 75.0},
                }
            },
            "ledger": [
                {
                    "uid": UID,
                    "before": 100.0,
                    "amount": -25.0,
                    "after": 75.0,
                    "reason": "withdraw:hold",
                    "meta": {"idempotency_key": "withdraw:hold:W-1", "req_id": "W-1"},
                }
            ],
            "withdrawal_seq": 1,
            "withdrawal_requests": {
                "W-1": {
                    "uid": UID,
                    "amount": 25.0,
                    "address": ADDRESS,
                    "status": "pending",
                    "created_at": 1_760_000_000.0,
                }
            },
        }

    def _resolve(self, action="approve", ref="TON-TX-REFERENCE-1"):
        return service.resolve_withdrawal(
            self.db,
            "W-1",
            action,
            ADMIN_UID,
            ref=ref,
        )

    def test_freeze_after_request_before_approval_leaves_request_pending(self):
        self.db["users"][UID]["frozen"] = True
        before = copy.deepcopy(self.db)

        with patch.dict(os.environ, {"WITHDRAWALS_OPEN": "1"}):
            with self.assertRaisesRegex(ValueError, "ACCOUNT_FROZEN"):
                self._resolve()

        self.assertEqual(self.db, before)
        self.assertEqual(self.db["withdrawal_requests"]["W-1"]["status"], "pending")
        self.assertEqual(self.db["users"][UID]["wallet"]["credits"], 75.0)

    def test_closed_gate_leaves_request_and_ledger_unchanged(self):
        before = copy.deepcopy(self.db)

        with patch.dict(os.environ, {"WITHDRAWALS_OPEN": "0"}):
            with self.assertRaisesRegex(ValueError, "WITHDRAWALS_CLOSED"):
                self._resolve()

        self.assertEqual(self.db, before)

    def test_valid_non_frozen_approval_marks_paid_only_with_payout_reference(self):
        before_balance = self.db["users"][UID]["wallet"]["credits"]
        before_ledger = copy.deepcopy(self.db["ledger"])

        with patch.dict(os.environ, {"WITHDRAWALS_OPEN": "1"}):
            result = self._resolve(ref="manual-payout-ref-abc")

        self.assertEqual(result["status"], "paid")
        self.assertEqual(result["paid_ref"], "manual-payout-ref-abc")
        self.assertEqual(result["resolved_by"], ADMIN_UID)
        self.assertEqual(self.db["users"][UID]["wallet"]["credits"], before_balance)
        self.assertEqual(self.db["ledger"], before_ledger)

    def test_duplicate_approval_is_rejected_without_any_second_mutation(self):
        with patch.dict(os.environ, {"WITHDRAWALS_OPEN": "1"}):
            self._resolve()
            after_first = copy.deepcopy(self.db)

            with self.assertRaisesRegex(ValueError, "REQUEST_NOT_PENDING"):
                self._resolve(ref="second-ref")

        self.assertEqual(self.db, after_first)

    def test_missing_payout_reference_does_not_change_request(self):
        before = copy.deepcopy(self.db)

        with patch.dict(os.environ, {"WITHDRAWALS_OPEN": "1"}):
            with self.assertRaisesRegex(ValueError, "REF_REQUIRED"):
                self._resolve(ref="")

        self.assertEqual(self.db, before)

    def test_malformed_amount_or_address_fails_closed_before_approval(self):
        for field, value in (("amount", float("nan")), ("amount", 0), ("address", "not-a-ton-address")):
            with self.subTest(field=field, value=value):
                self.setUp()
                self.db["withdrawal_requests"]["W-1"][field] = value
                before = copy.deepcopy(self.db)

                with patch.dict(os.environ, {"WITHDRAWALS_OPEN": "1"}):
                    with self.assertRaisesRegex(ValueError, "WITHDRAWAL_RECORD_INVALID"):
                        self._resolve()

                self.assertEqual(self.db, before)

    def test_frozen_account_can_be_refunded_via_rejection_without_being_marked_paid(self):
        self.db["users"][UID]["frozen"] = True
        before_balance = self.db["users"][UID]["wallet"]["credits"]

        result = self._resolve(action="reject")

        self.assertEqual(result["status"], "rejected")
        self.assertEqual(self.db["users"][UID]["wallet"]["credits"], before_balance + 25.0)
        self.assertEqual(self.db["ledger"][-1]["reason"], "withdraw:refund")
        self.assertEqual(self.db["ledger"][-1]["amount"], 25.0)
        self.assertNotIn("paid_ref", result)

        after_first = copy.deepcopy(self.db)
        with self.assertRaisesRegex(ValueError, "REQUEST_NOT_PENDING"):
            self._resolve(action="reject")
        self.assertEqual(self.db, after_first)


if __name__ == "__main__":
    unittest.main()
