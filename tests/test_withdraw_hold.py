import math
import unittest
from pathlib import Path

from handlers.withdraw_request_handler import create_withdrawal, resolve_withdrawal

ADDR = "UQCd7XHWGj06cBLlWW_DZUN3TWMGr_oWoVy0G0LkC14gQklj"


def make_db(credits=10.0):
    return {
        "users": {"1": {"wallet": {"credits": credits}}},
        "ledger": [],
    }


class WithdrawTests(unittest.TestCase):
    def test_hold_deducts_credits_and_records_idempotent_ledger_entry(self):
        db = make_db()
        req_id = create_withdrawal(db, "1", 4.0, ADDR)

        self.assertEqual(db["users"]["1"]["wallet"]["credits"], 6.0)
        self.assertEqual(db["withdrawal_requests"][req_id]["status"], "pending")
        self.assertEqual(db["ledger"][-1]["reason"], "withdraw:hold")
        self.assertEqual(
            db["ledger"][-1]["meta"]["idempotency_key"],
            f"withdraw:hold:{req_id}",
        )

    def test_cannot_request_more_than_remaining_balance(self):
        db = make_db(10.0)
        create_withdrawal(db, "1", 10.0, ADDR)

        with self.assertRaises(ValueError):
            create_withdrawal(db, "1", 1.0, ADDR)

        self.assertEqual(db["users"]["1"]["wallet"]["credits"], 0.0)

    def test_invalid_amounts_are_rejected_without_mutation(self):
        for amount in (float("nan"), float("inf"), float("-inf"), -1.0, 0.0, 0.5):
            with self.subTest(amount=amount):
                db = make_db()
                with self.assertRaises(ValueError):
                    create_withdrawal(db, "1", amount, ADDR)
                self.assertEqual(db["users"]["1"]["wallet"]["credits"], 10.0)
                self.assertEqual(db["ledger"], [])
                self.assertNotIn("withdrawal_requests", db)

    def test_invalid_address_is_rejected_without_mutation(self):
        db = make_db()
        with self.assertRaises(ValueError):
            create_withdrawal(db, "1", 1.0, "not-a-ton-address")
        self.assertEqual(db["users"]["1"]["wallet"]["credits"], 10.0)
        self.assertEqual(db["ledger"], [])

    def test_unknown_user_is_rejected(self):
        with self.assertRaises(ValueError):
            create_withdrawal(make_db(), "missing", 1.0, ADDR)

    def test_request_ids_do_not_collide(self):
        db = make_db()
        first = create_withdrawal(db, "1", 1.0, ADDR)
        second = create_withdrawal(db, "1", 1.0, ADDR)
        self.assertNotEqual(first, second)
        self.assertEqual(len(db["withdrawal_requests"]), 2)

    def test_rejection_refunds_exactly_once(self):
        db = make_db()
        req_id = create_withdrawal(db, "1", 4.0, ADDR)

        resolve_withdrawal(db, req_id, "reject", "9")

        self.assertEqual(db["users"]["1"]["wallet"]["credits"], 10.0)
        self.assertEqual(db["withdrawal_requests"][req_id]["status"], "rejected")
        self.assertEqual(db["ledger"][-1]["reason"], "withdraw:refund")
        self.assertEqual(
            db["ledger"][-1]["meta"]["idempotency_key"],
            f"withdraw:refund:{req_id}",
        )
        with self.assertRaises(ValueError):
            resolve_withdrawal(db, req_id, "reject", "9")
        self.assertEqual(db["users"]["1"]["wallet"]["credits"], 10.0)

    def test_approval_requires_payout_reference_and_is_final(self):
        db = make_db()
        req_id = create_withdrawal(db, "1", 4.0, ADDR)

        with self.assertRaises(ValueError):
            resolve_withdrawal(db, req_id, "approve", "9")

        result = resolve_withdrawal(db, req_id, "approve", "9", "manual-payout-ref")
        self.assertEqual(result["status"], "paid")
        self.assertEqual(result["paid_ref"], "manual-payout-ref")
        # Approval records a manually completed payout; it never triggers an on-chain transfer.
        self.assertEqual(db["users"]["1"]["wallet"]["credits"], 6.0)
        with self.assertRaises(ValueError):
            resolve_withdrawal(db, req_id, "reject", "9")
        self.assertEqual(db["users"]["1"]["wallet"]["credits"], 6.0)

    def test_runtime_loader_includes_withdrawal_handler(self):
        loader = Path("handlers/loader.py").read_text(encoding="utf-8")
        self.assertIn(
            '("withdraw", "handlers.withdraw_request_handler")',
            loader,
        )


if __name__ == "__main__":
    unittest.main()
