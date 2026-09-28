import unittest

from core.asset_truth import build_slH_asset_truth


class AssetTruthTests(unittest.TestCase):
    def test_legacy_internal_balance_is_not_promoted_to_live(self):
        truth = build_slH_asset_truth({
            "token_balance": 50000,
            "exchange_reserved_slh": 0,
        })

        self.assertEqual(truth["current_total"], 50000)
        self.assertEqual(truth["current_live"], 0)
        self.assertEqual(truth["current_reserved"], 0)
        self.assertEqual(truth["legacy_internal"], 50000)
        self.assertEqual(truth["spendable_live"], 0)
        self.assertEqual(truth["provenance_status"], "legacy_internal")

    def test_live_balance_excludes_reserved_amount_from_spendable(self):
        truth = build_slH_asset_truth({
            "token_balance": 120,
            "live_token_balance": 120,
            "exchange_reserved_slh": 30,
        })

        self.assertEqual(truth["current_total"], 120)
        self.assertEqual(truth["current_live"], 120)
        self.assertEqual(truth["current_reserved"], 30)
        self.assertEqual(truth["legacy_internal"], 0)
        self.assertEqual(truth["spendable_live"], 90)
        self.assertEqual(truth["provenance_status"], "live_backed")

    def test_empty_wallet_is_empty(self):
        truth = build_slH_asset_truth({})

        self.assertEqual(truth["current_total"], 0)
        self.assertEqual(truth["current_live"], 0)
        self.assertEqual(truth["current_reserved"], 0)
        self.assertEqual(truth["legacy_internal"], 0)
        self.assertEqual(truth["spendable_live"], 0)
        self.assertEqual(truth["provenance_status"], "empty")


if __name__ == "__main__":
    unittest.main()
