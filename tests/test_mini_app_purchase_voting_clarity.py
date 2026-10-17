from pathlib import Path
import unittest


MINI_APP = (Path(__file__).resolve().parents[1] / "mini_app.html").read_text(encoding="utf-8")


class MiniAppPurchaseVotingClarityTests(unittest.TestCase):
    def test_market_explains_each_purchase_grant_and_asset_boundary(self):
        for fragment in (
            'id="marketAssetGuide"',
            "קורסים מעניקים גישה",
            "Credits הם יתרה פנימית",
            "רכישה בחנות אינה מקנה זכות הצבעה אוטומטית",
            "SLH on-chain",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, MINI_APP)

    def test_governance_explains_the_current_role_based_vote_model(self):
        self.assertIn('id="governanceRulesNotice"', MINI_APP)
        self.assertIn("משקל ההצבעה נגזר מתפקיד החשבון", MINI_APP)
        self.assertIn("לא מיתרת SLH", MINI_APP)

    def test_exchange_receipt_reports_all_fresh_canonical_checks_in_hebrew(self):
        self.assertIn("בדיקת המסחר העדכנית: עברה", MINI_APP)
        for fragment in (
            "שער ציבורי",
            "ספר פקודות",
            "תקינות עסקאות",
            "איזון יתרות כספיות",
            "אימות סביבת ההרצה בזמן אמת",
            "שער הפריסה / שער המסחר הציבורי",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, MINI_APP)

        receipt_start = MINI_APP.index("function renderExchangeExecutionReceipt")
        receipt_end = MINI_APP.index("function renderExchangeExecutionBlocked", receipt_start)
        receipt = MINI_APP[receipt_start:receipt_end]
        for legacy_label in (
            "Fresh Exchange check: PASS",
            "Order ID:",
            "Filled:",
            "Remaining:",
            "Trade ID:",
            "Live runtime confirmation",
            "Railway gate / live gate",
            "Live verdict / readiness",
        ):
            with self.subTest(legacy_label=legacy_label):
                self.assertNotIn(legacy_label, receipt)


if __name__ == "__main__":
    unittest.main()
