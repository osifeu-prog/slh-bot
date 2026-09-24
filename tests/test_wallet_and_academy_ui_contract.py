import unittest
from pathlib import Path


class WalletAndAcademyUiContractTests(unittest.TestCase):
    def test_wallet_copy_is_binding_aware_not_globally_paused(self):
        source = Path("handlers/wallet_handler.py").read_text(encoding="utf-8")
        self.assertNotIn("מושהים כרגע עד להשלמת user-binding מאומת", source)
        self.assertIn("get_binding", source)
        self.assertIn("get_ton_binding", source)
        self.assertIn("TON_DEPOSITS_OPEN", source)

    def test_mini_app_has_no_staking_academy_prerequisite_claim(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertNotIn("כדי לפתוח Staking: התחל קורס", source)
        self.assertIn("Academy הוא מסלול למידה נפרד", source)


if __name__ == "__main__":
    unittest.main()
