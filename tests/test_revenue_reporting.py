"""Regression tests for source-validated Stars revenue reporting."""

import copy
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from core import revenue_ledger
from handlers import business_control_handler, revenue_handler


class RevenueReportingFilterTests(unittest.TestCase):
    def setUp(self):
        now = datetime.now(timezone.utc).isoformat()
        credits = [
            ("credit-charge-1", "1001", 100),
            ("credit-charge-2", "1002", 100),
        ]
        items = [
            ("item-charge-1", "2001", "agent_os", 199),
            ("item-charge-2", "2002", "emoji_vip", 199),
            ("item-charge-3", "2003", "emoji_bitcoin", 25),
        ]
        revenue = []
        transactions = []
        ledger = []
        subscriptions = {}
        orders = {}

        for charge, uid, amount in credits:
            revenue.append({
                "timestamp": now,
                "source": "telegram_stars",
                "amount": amount,
                "currency": "XTR",
                "reference": charge,
                "uid": uid,
                "meta": {"kind": "telegram_stars_gross"},
            })
            transactions.append({
                "uid": uid,
                "credits": 100,
                "stars_paid": amount,
                "currency": "XTR",
                "telegram_payment_charge_id": charge,
            })
            ledger.append({
                "uid": uid,
                "reason": "payment:telegram_stars",
                "meta": {
                    "source": "telegram_successful_payment",
                    "charge_id": charge,
                    "currency": "XTR",
                    "stars_paid": amount,
                    "test_mode": False,
                },
            })

        revenue.append({
            "timestamp": now,
            "source": "telegram_stars_subscription",
            "amount": 499,
            "currency": "XTR",
            "reference": "vip-charge",
            "uid": "3001",
            "meta": {"kind": "vip_monthly"},
        })
        subscriptions["vip-charge"] = {
            "charge_id": "vip-charge",
            "uid": "3001",
            "stars_paid": 499,
            "status": "ACTIVE",
            "fulfillment_status": "completed",
        }

        for charge, uid, item_id, amount in items:
            revenue.append({
                "timestamp": now,
                "source": "telegram_stars_item",
                "amount": amount,
                "currency": "XTR",
                "reference": charge,
                "uid": uid,
                "meta": {"kind": "telegram_stars_item", "item_id": item_id},
            })
            orders["stars:" + charge] = {
                "charge_id": charge,
                "uid": uid,
                "item_id": item_id,
                "stars_paid": amount,
                "status": "FULFILLED",
            }

        self.test_row = {
            "timestamp": now,
            "source": "telegram_stars",
            "amount": 100,
            "currency": "XTR",
            "reference": "boundary-test-case",
            "uid": "test_user",
            "meta": {"test": False, "is_test": False},
        }
        self.orphan_row = {
            "timestamp": now,
            "source": "telegram_stars",
            "amount": 77,
            "currency": "XTR",
            "reference": "orphan-charge",
            "uid": "4001",
            "meta": {},
        }
        self.db = {
            "users": {},
            "transactions": transactions,
            "ledger": ledger,
            "vip_subscriptions": subscriptions,
            "star_item_orders": orders,
            "revenue_ledger": revenue + [self.test_row, self.orphan_row],
        }

    def test_canonical_xtr_rows_only_include_source_validated_payments(self):
        rows = revenue_handler._canonical_xtr_rows(self.db)
        self.assertEqual(len(rows), 6)
        self.assertEqual(sum(row["amount"] for row in rows), 1122)
        self.assertNotIn(self.test_row, rows)
        self.assertNotIn(self.orphan_row, rows)

    def test_business_and_period_reports_exclude_test_and_unmatched_rows(self):
        with (
            patch.object(business_control_handler.state_manager, "load_db", return_value=self.db),
            patch.object(business_control_handler, "_registered_bot_count", return_value=0),
        ):
            business = business_control_handler._business_summary()
            period = business_control_handler._revenue_report(30)
        self.assertIn("Verified gross receipts (not profit): 1122 XTR", business)
        self.assertIn("Revenue events: 6", business)
        self.assertIn("אירועי תקבול ברוטו שעברו אימות מקומי: 6", period)
        self.assertIn("XTR: 1122", period)
        self.assertNotIn("1222", business + period)
        self.assertNotIn("1299", business + period)

    def test_audit_separates_excluded_rows_without_mutating_ledger(self):
        before = copy.deepcopy(self.db)
        with patch.object(revenue_ledger.state_manager, "load_db", return_value=self.db):
            audit = revenue_ledger.summary()
        self.assertEqual(audit["events"], 6)
        self.assertEqual(audit["raw_events"], 8)
        self.assertEqual(audit["excluded_test_events"], 1)
        self.assertEqual(audit["totals"], {"XTR": 1122.0})
        self.assertEqual(audit["excluded_test_totals"], {"XTR": 100.0})
        self.assertEqual(audit["excluded_unverified_events"], 1)
        self.assertEqual(audit["excluded_unverified_totals"], {"XTR": 77.0})
        self.assertEqual(self.db, before)

    def test_store_rows_require_an_explicit_matching_item_id(self):
        original_item = next(
            row for row in self.db["revenue_ledger"]
            if row.get("source") == "telegram_stars_item"
        )
        reference = original_item["reference"]
        amount = original_item["amount"]

        for invalid_item_id in ("", "different-item"):
            with self.subTest(item_id=invalid_item_id or "<missing>"):
                db = copy.deepcopy(self.db)
                row = next(
                    item for item in db["revenue_ledger"]
                    if item.get("reference") == reference
                    and item.get("source") == "telegram_stars_item"
                )
                row["meta"]["item_id"] = invalid_item_id
                before = copy.deepcopy(db)

                reportable = revenue_ledger.reportable_rows(db, currency="XTR")
                refs = {item["reference"] for item in reportable}
                self.assertNotIn(reference, refs)
                self.assertEqual(len(reportable), 5)
                self.assertEqual(
                    sum(item["amount"] for item in reportable),
                    1122 - amount,
                )
                self.assertEqual(db, before)

    def test_reportable_filter_is_read_only_and_rejects_invalid_rows(self):
        db = copy.deepcopy(self.db)
        db["revenue_ledger"].extend([
            {
                "source": "telegram_stars",
                "amount": 50,
                "currency": "XTR",
                "reference": "",
                "uid": "5001",
            },
            {
                "source": "telegram_stars_item",
                "amount": -5,
                "currency": "XTR",
                "reference": "charge-negative",
                "uid": "5002",
            },
        ])
        before = copy.deepcopy(db)
        self.assertEqual(len(revenue_ledger.reportable_rows(db, currency="XTR")), 6)
        self.assertEqual(db, before)


if __name__ == "__main__":
    unittest.main()
