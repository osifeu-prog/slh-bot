import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PhysicalMarketplaceContractTest(unittest.TestCase):
    def test_physical_purchase_is_canonical_and_atomic(self):
        source = (ROOT / "store" / "purchase_service.py").read_text(encoding="utf-8")
        self.assertIn("def purchase_physical", source)
        self.assertIn('state_manager.atomic_update(mutate)', source)
        self.assertIn('"store:p2p_purchase"', source)
        self.assertIn('"store:p2p_sale"', source)
        self.assertIn('"store:commission"', source)
        self.assertIn('"status": "PAID"', source)
        self.assertNotIn('grant(str(seller_uid)', source)

    def test_physical_catalog_entries_are_not_hardware(self):
        items = json.loads((ROOT / "store" / "items.json").read_text(encoding="utf-8"))
        for item_id in ("bill_100_ils", "bill_200_ils", "test_bill", "bill_50_ils", "bill_20_ils"):
            self.assertEqual(items[item_id]["type"], "physical")
            self.assertIn("physical", items[item_id]["grant"])

    def test_user_market_handler_is_registered(self):
        loader = (ROOT / "handlers" / "loader.py").read_text(encoding="utf-8")
        handler = (ROOT / "handlers" / "user_shop_handler.py").read_text(encoding="utf-8")
        self.assertIn('("user_shop", "handlers.user_shop_handler")', loader)
        for command in ('commands=["sell"]', 'commands=["my_products"]', 'commands=["umarket"]', 'commands=["unsell"]'):
            self.assertIn(command, handler)


if __name__ == "__main__":
    unittest.main()
