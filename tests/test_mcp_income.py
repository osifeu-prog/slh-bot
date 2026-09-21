import unittest


class MCPIncomeTests(unittest.TestCase):
    def test_income_status_exposes_p0_and_real_channels(self):
        from slh_mcp.tools.income import income_status_tool

        result = income_status_tool()
        self.assertEqual(result["priority"], "P0")
        ids = {row["id"] for row in result["paths"]}
        self.assertIn("telegram_stars_credits", ids)
        self.assertIn("telegram_stars_store", ids)
        self.assertIn("manual_shop_ils_ton", ids)


if __name__ == "__main__":
    unittest.main()
