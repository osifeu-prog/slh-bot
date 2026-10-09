import unittest

from handlers.exchange_handler import format_execution_receipt


class ExchangeExecutionReceiptTests(unittest.TestCase):
    def setUp(self):
        self.result = {
            "order_id": "O0000000042",
            "filled": "0.00000000",
            "remaining": "1.00000000",
            "status": "open",
            "trade_ids": [],
            "execution_check": {
                "status": "PASS",
                "checked_at": "2026-10-10T00:00:00+00:00",
                "public_gate": "OPEN",
                "verdict": "OPEN",
                "execution_ready": True,
                "public_ready": True,
                "order_book_integrity": True,
                "trade_integrity": True,
                "money_invariants": True,
                "open_orders_before": 0,
            },
        }

    def test_receipt_surfaces_fresh_canonical_pass_and_order_details(self):
        receipt = format_execution_receipt("buy", self.result)

        self.assertIn("BUY #O0000000042", receipt)
        self.assertIn("Fresh canonical Exchange check: PASS", receipt)
        self.assertIn("2026-10-10T00:00:00+00:00", receipt)
        self.assertIn("Gate: OPEN", receipt)
        self.assertIn("execution_ready: PASS", receipt)
        self.assertIn("order_book_integrity: PASS", receipt)
        self.assertIn("trade_integrity: PASS", receipt)
        self.assertIn("money_invariants: PASS", receipt)

    def test_missing_check_evidence_never_claims_pass(self):
        result = {key: value for key, value in self.result.items() if key != "execution_check"}

        receipt = format_execution_receipt("sell", result)

        self.assertIn("Fresh canonical Exchange check: NOT VERIFIED", receipt)
        self.assertNotIn("Fresh canonical Exchange check: PASS", receipt)

    def test_partial_or_failed_check_never_claims_pass(self):
        result = dict(self.result)
        result["execution_check"] = dict(self.result["execution_check"])
        result["execution_check"]["money_invariants"] = False

        receipt = format_execution_receipt("buy", result)

        self.assertIn("Fresh canonical Exchange check: BLOCKED", receipt)
        self.assertIn("money_invariants: FAIL", receipt)
        self.assertNotIn("Fresh canonical Exchange check: PASS", receipt)


if __name__ == "__main__":
    unittest.main()
