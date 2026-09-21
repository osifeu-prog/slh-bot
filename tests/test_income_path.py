import unittest

from core.income_path import income_status


class IncomePathTests(unittest.TestCase):
    def test_priority_is_p0(self):
        status = income_status()
        self.assertEqual(status["priority"], "P0")

    def test_stars_paths_are_present(self):
        rows = {row["id"]: row for row in income_status()["paths"]}
        self.assertEqual(rows["telegram_stars_credits"]["status"], "implemented_automated")
        self.assertEqual(rows["telegram_stars_store"]["status"], "implemented_automated")

    def test_manual_and_paused_paths_are_explicit(self):
        rows = {row["id"]: row for row in income_status()["paths"]}
        self.assertEqual(rows["manual_shop_ils_ton"]["status"], "manual_unclosed")
        self.assertEqual(rows["ton_deposit_to_credits"]["status"], "paused")
        self.assertEqual(rows["withdrawal"]["status"], "manual_unclosed")


if __name__ == "__main__":
    unittest.main()
