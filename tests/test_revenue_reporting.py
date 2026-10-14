"""Regression tests for excluding synthetic Stars rows from revenue reports."""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from core import revenue_ledger
from handlers import business_control_handler, revenue_handler


class RevenueReportingFilterTests(unittest.TestCase):
    def setUp(self):
        now = datetime.now(timezone.utc).isoformat()
        self.db = {
            "users": {},
            "star_item_orders": {},
            "vip_subscriptions": {},
            "revenue_ledger": [
                {
                    "timestamp": now,
                    "source": "telegram_stars",
                    "amount": 300,
                    "currency": "XTR",
                    "reference": "charge-real-a",
                    "uid": "1001",
                    "meta": {},
                },
                {
                    "timestamp": now,
                    "source": "telegram_stars_item",
                    "amount": 822,
                    "currency": "XTR",
                    "reference": "charge-real-b",
                    "uid": "1002",
                    "meta": {},
                },
                {
                    "timestamp": now,
                    "source": "telegram_stars",
                    "amount": 100,
                    "currency": "XTR",
                    "reference": "boundary-test-case",
                    "uid": "test_user",
                    "meta": {"test": False, "is_test": False},
                },
            ],
        }

    def test_canonical_xtr_rows_excludes_boundary_test_row(self):
        rows = revenue_handler._canonical_xtr_rows(self.db)
        self.assertEqual([row["amount"] for row in rows], [300, 822])
        self.assertEqual(sum(row["amount"] for row in rows), 1122)

    def test_business_and_period_reports_exclude_test_revenue(self):
        with (
            patch.object(business_control_handler.state_manager, "load_db", return_value=self.db),
            patch.object(business_control_handler, "_registered_bot_count", return_value=0),
        ):
            business = business_control_handler._business_summary()
            period = business_control_handler._revenue_report(30)
        self.assertIn("Verified revenue: 1122 XTR", business)
        self.assertIn("Revenue events: 2", business)
        self.assertIn("אירועי הכנסה מאומתים: 2", period)
        self.assertIn("XTR: 1122", period)
        self.assertNotIn("1222", business + period)

    def test_audit_separates_excluded_rows_without_mutating_ledger(self):
        before = repr(self.db)
        with patch.object(revenue_ledger.state_manager, "load_db", return_value=self.db):
            audit = revenue_ledger.summary()
        self.assertEqual(audit["events"], 2)
        self.assertEqual(audit["raw_events"], 3)
        self.assertEqual(audit["excluded_test_events"], 1)
        self.assertEqual(audit["totals"], {"XTR": 1122.0})
        self.assertEqual(audit["excluded_test_totals"], {"XTR": 100.0})
        self.assertEqual(repr(self.db), before)

    def test_reportable_filter_is_read_only_and_rejects_invalid_rows(self):
        before = repr(self.db)
        db = {
            "revenue_ledger": self.db["revenue_ledger"] + [
                {
                    "amount": 50,
                    "currency": "XTR",
                    "reference": "",
                    "uid": "1003",
                },
                {
                    "amount": -5,
                    "currency": "XTR",
                    "reference": "charge-negative",
                    "uid": "1004",
                },
            ]
        }
        self.assertEqual(len(revenue_ledger.reportable_rows(db, currency="XTR")), 2)
        self.assertEqual(repr(self.db), before)


if __name__ == "__main__":
    unittest.main()
