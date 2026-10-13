import unittest

from core.slh_exchange_reconciliation import audit_db


class ExchangeReconciliationTests(unittest.TestCase):
    def test_cancelled_sell_with_manual_correction_is_not_passed(self):
        db = {
            "exchange_order_archive": {
                "O0000000009": {
                    "id": "O0000000009", "uid": "6526198118", "uid_suffix": "8118", "side": "sell",
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
        missing_release = next(item for item in report["findings"] if item["code"] == "CANCELLED_SELL_ORDER_MISSING_NORMAL_RELEASE")
        self.assertEqual(missing_release["uid_suffix"], "8118")
        correction = next(item for item in report["findings"] if item["code"] == "MANUAL_RESERVE_CORRECTION_REQUIRES_REVIEW")
        self.assertEqual(correction["correction_delta"], "10000")

    def test_normal_release_balances_legacy_ledger_reserve(self):
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

    def test_canonical_token_ledger_positive_amounts_balance_by_event_kind(self):
        db = {
            "exchange_orders": {
                "O2": {"id": "O2", "uid": "42", "side": "sell", "status": "cancelled"}
            },
            "ledger": [],
            "slh_token_ledger": [
                {
                    "event_id": "exchange:reserve_slh:O2",
                    "from_uid": "42",
                    "to_uid": "__EXCHANGE_RESERVE__",
                    "amount": 100.0,
                    "reason": "exchange:sell_reserve",
                    "kind": "exchange_reserve",
                    "order_id": "O2",
                },
                {
                    "event_id": "exchange:release_slh:O2",
                    "from_uid": "__EXCHANGE_RESERVE__",
                    "to_uid": "42",
                    "amount": 100.0,
                    "reason": "exchange:cancel_release_slh",
                    "kind": "exchange_release",
                    "order_id": "O2",
                },
            ],
        }
        report = audit_db(db)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["finding_count"], 0)

    def test_no_matched_reserves_is_unknown_not_pass(self):
        report = audit_db({"exchange_orders": {}, "ledger": [], "slh_token_ledger": []})
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertIn("NO_CANCELLED_SELL_ORDERS_WITH_RESERVE_FOUND", {item["code"] for item in report["findings"]})

    def test_invalid_reserve_amount_fails_closed(self):
        db = {
            "exchange_orders": {
                "O2": {"id": "O2", "uid": "42", "side": "sell", "status": "cancelled"}
            },
            "ledger": [
                {"uid": "42", "amount": None, "reason": "exchange:sell_reserve",
                 "meta": {"order_id": "O2", "event_id": "reserve:O2"}},
                {"uid": "42", "amount": 100, "reason": "exchange:cancel_release",
                 "meta": {"order_id": "O2", "event_id": "release:O2"}},
            ],
            "slh_token_ledger": [],
        }
        report = audit_db(db)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("INVALID_RESERVE_LEDGER_AMOUNT", {item["code"] for item in report["findings"]})

    def test_audit_never_mutates_input(self):
        db = {"exchange_orders": {}, "ledger": [], "slh_token_ledger": []}
        before = repr(db)
        audit_db(db)
        self.assertEqual(repr(db), before)


if __name__ == "__main__":
    unittest.main()
