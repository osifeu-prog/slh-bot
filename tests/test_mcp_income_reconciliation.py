import unittest
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class MCPIncomeReconciliationTests(unittest.TestCase):
    def setUp(self):
        from slh_mcp.auth import Principal
        self.owner = Principal(
            subject=str(OWNER_TELEGRAM_ID),
            role="OWNER",
            permissions=frozenset(),
        )

    def test_reconciliation_detects_missing_revenue(self):
        from slh_mcp.tools.income import income_reconciliation

        db = {
            "transactions": [
                {
                    "uid": str(OWNER_TELEGRAM_ID),
                    "currency": "XTR",
                    "stars_paid": 100,
                    "telegram_payment_charge_id": "charge-1",
                }
            ],
            "revenue_ledger": [],
            "vip_subscriptions": {},
            "star_item_orders": {},
        }
        with patch("slh_mcp.tools.income.state_manager.load_db", return_value=db):
            result = income_reconciliation(self.owner)

        self.assertEqual(result["status"], "ATTENTION")
        self.assertEqual(result["missing_count"], 1)
        self.assertEqual(result["missing_revenue"][0]["reference"], "charge-1")

    def test_reconciliation_requires_audit_permission(self):
        from slh_mcp.auth import Principal
        from slh_mcp.tools.income import income_reconciliation

        principal = Principal(
            subject=str(OWNER_TELEGRAM_ID),
            role="OWNER",
            permissions=frozenset(),
        )
        with patch("slh_mcp.tools.income.authorize", return_value=False):
            with self.assertRaises(PermissionError):
                income_reconciliation(principal)


if __name__ == "__main__":
    unittest.main()
