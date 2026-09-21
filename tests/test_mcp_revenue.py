import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class MCPRevenueTests(unittest.TestCase):
    def test_revenue_status_uses_canonical_ledger(self):
        from slh_mcp.tools.revenue import revenue_status

        with patch(
            "slh_mcp.tools.revenue.revenue_ledger.summary",
            return_value={"events": 3, "totals": {"XTR": 1497}},
        ):
            result = revenue_status()

        self.assertEqual(result["events"], 3)
        self.assertEqual(result["totals"]["XTR"], 1497)
        self.assertEqual(
            result["source_of_truth"],
            "state.db.json:revenue_ledger",
        )

    def test_revenue_events_are_read_only(self):
        from slh_mcp.tools.revenue import revenue_events

        fake = {
            "revenue_ledger": [
                {"source": "telegram_stars", "amount": 499, "currency": "XTR", "reference": "r1"}
            ]
        }
        with patch("slh_mcp.tools.revenue.state_manager.load_db", return_value=fake):
            result = revenue_events()

        self.assertEqual(result[0]["amount"], 499)
        self.assertEqual(fake["revenue_ledger"][0]["amount"], 499)


if __name__ == "__main__":
    unittest.main()
