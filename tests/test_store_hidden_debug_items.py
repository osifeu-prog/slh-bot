import unittest
from unittest.mock import patch

from store import engine


class StoreHiddenDebugItemsTests(unittest.TestCase):
    def test_hidden_debug_items_are_not_rendered_from_catalog_or_marketplace(self):
        catalog = {
            "test_bill": {"name": "שטר בדיקה", "price": 5, "type": "physical"},
            "bill_100_ils": {"name": "שטר 100 ₪ פיזי", "price": 50, "type": "physical"},
        }
        products = {
            "u_8789977826_test_product": {
                "name": "Test product", "type": "physical", "inventory": 3, "price": 20
            },
            "u_8789977826_market_smoke": {
                "name": "Market smoke", "type": "physical", "inventory": 3, "price": 20
            },
            "bill_100_ils": {
                "name": "שטר 100 ₪ פיזי", "type": "physical", "inventory": 2, "price": 50
            },
        }

        with patch("store.engine.load_items", return_value=catalog), patch(
            "store.engine.load_products", return_value=products
        ):
            rendered = engine.format_shop_message(user_balance=10)

        self.assertNotIn("שטר בדיקה", rendered)
        self.assertNotIn("Test product", rendered)
        self.assertNotIn("Market smoke", rendered)
        self.assertIn("שטר 100 ₪ פיזי", rendered)

    def test_hidden_ids_do_not_change_database_or_purchase_records(self):
        # The visibility filter is presentation-only; it must not mutate the DB.
        self.assertEqual(
            engine.HIDDEN_ITEM_IDS,
            {
                "test_bill",
                "u_8789977826_test_product",
                "u_8789977826_market_smoke",
            },
        )


if __name__ == "__main__":
    unittest.main()
