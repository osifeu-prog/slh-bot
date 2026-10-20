import unittest

from core.ask_router import detect_intent


class LedgerIntentRoutingTests(unittest.TestCase):
    def test_numeric_alpha_gap_routes_to_ledger(self):
        self.assertEqual(
            detect_intent("תסביר לי את הפער של 10499 בין 1316 ל-11815"),
            "ledger",
        )

    def test_other_ledger_gaps_route_to_ledger(self):
        self.assertEqual(detect_intent("מה עם 2 הפערים האחרים?"), "ledger")
        self.assertEqual(detect_intent("what does alpha_consolidate mean?"), "ledger")

    def test_staking_question_still_routes_to_staking(self):
        self.assertEqual(detect_intent("כמה סטייק יש לי?"), "staking")


if __name__ == "__main__":
    unittest.main()
