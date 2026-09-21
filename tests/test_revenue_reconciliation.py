import unittest

from core import revenue_reconciliation


class RevenueReconciliationTests(unittest.TestCase):
    def test_detects_missing_stars_revenue(self):
        db = {
            "transactions": [
                {
                    "uid": "1",
                    "currency": "XTR",
                    "stars_paid": 100,
                    "telegram_payment_charge_id": "credits-charge-1",
                }
            ],
            "revenue_ledger": [],
            "vip_subscriptions": {},
            "star_item_orders": {},
        }
        result = revenue_reconciliation.audit(db)
        self.assertEqual(result["status"], "ATTENTION")
        self.assertEqual(result["missing_revenue"][0]["reference"], "credits-charge-1")

    def test_covered_vip_subscription_is_not_missing(self):
        db = {
            "transactions": [],
            "revenue_ledger": [
                {
                    "source": "telegram_stars_subscription",
                    "reference": "vip-charge-1",
                    "amount": 499,
                    "currency": "XTR",
                }
            ],
            "vip_subscriptions": {
                "vip-charge-1": {
                    "uid": "1",
                    "stars_paid": 499,
                    "status": "ACTIVE",
                }
            },
            "star_item_orders": {},
        }
        result = revenue_reconciliation.audit(db)
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["missing_revenue"], [])

    def test_recoverable_store_order_is_flagged(self):
        db = {
            "transactions": [],
            "revenue_ledger": [],
            "vip_subscriptions": {},
            "star_item_orders": {
                "stars:item-charge-1": {
                    "uid": "1",
                    "charge_id": "item-charge-1",
                    "stars_paid": 199,
                    "status": "RECOVERABLE",
                    "item_id": "agent_os",
                }
            },
        }
        result = revenue_reconciliation.audit(db)
        self.assertEqual(result["status"], "ATTENTION")
        self.assertEqual(result["missing_revenue"][0]["reference"], "item-charge-1")
        self.assertEqual(result["missing_revenue"][0]["reason"], "FULFILLMENT_RECOVERABLE")


if __name__ == "__main__":
    unittest.main()
