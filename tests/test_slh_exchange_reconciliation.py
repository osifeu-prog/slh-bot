import unittest

from core.slh_exchange_reconciliation import audit_db


class ExchangeReconciliationTests(unittest.TestCase):
    def test_cancelled_sell_with_manual_correction_is_not_passed(self):
        db = {
            "exchange_order_archive": {
                "O0000000009": {
                    "id": "O0000000009", "uid": "6526198118", "side": "sell",
                    "status": "cancelled", "original_amount": "10000", "remaining_amount": "0"
                }
            },
            "ledger": [
                {"uid": "6526198118", "amount": -10000, "reason": "exchange:sell_reserve",
                 "meta": {"order_id": "O0000000009"}},
                {"uid": "6526198118", "amount": 10000, "reason": "exchange:missed_release_correction",
                 "meta": {"order_id": "O0000000009", "event_id": "correction:O0000000009"}},
            ],
            "slh_token_ledger": [],
        }
        report = audit_db(db)
        codes = {item["code"] for item in report["findings"]}
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("CANCELLED_SELL_ORDER_MISSING_NORMAL_RELEASE", codes)
        self.assertIn("MANUAL_RESERVE_CORRECTION_REQUIRES_REVIEW", codes)
        correction = next(item for item in report["findings"] if item["code"] == "MANUAL_RESERVE_CORRECTION_REQUIRES_REVIEW")
        self.assertEqual(correction["correction_delta"], "10000")

    def test_normal_release_balances_reserve(self):
        db = {
            "exchange_orders": {
                "O1": {"id": "O1", "uid": "42", "side": "sell", "status": "cancelled"}
            },
            "ledger": [
                {"uid": "42", "amount": -100, "reason": "exchange:sell_reserve",
                 "meta": {"order_id": "O1"}},
                {"uid": "42", "amount": 100, "reason": "exchange:cancel_release",
                 "meta": {"order_id": "O1"}},
            ],
            "slh_token_ledger": [],
        }
        report = audit_db(db)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["finding_count"], 0)

    def test_audit_never_mutates_input(self):
        db = {"exchange_orders": {}, "ledger": [], "slh_token_ledger": []}
        before = repr(db)
        audit_db(db)
        self.assertEqual(repr(db), before)


if __name__ == "__main__":
    unittest.main()
