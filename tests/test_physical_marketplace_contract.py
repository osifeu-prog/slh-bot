import json
from pathlib import Path
import unittest
from unittest.mock import patch

from core.account_ledger_audit import audit_account_ledger
from store import purchase_service


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


    def test_physical_sale_fails_closed_when_seller_wallet_differs_from_ledger_tail(self):
        db = {
            "users": {
                "buyer": {"wallet": {"credits": 1.0}},
                "seller": {"wallet": {"credits": 6.191775}},
            },
            "products": {
                "item": {
                    "type": "physical", "seller_uid": "seller",
                    "price": 1.0, "inventory": 1,
                }
            },
            "purchases": {},
            "ledger": [
                {"uid": "buyer", "before": 0.0, "amount": 1.0,
                 "after": 1.0, "reason": "test:opening"},
                {"uid": "seller", "before": 0.191775, "amount": 1.0,
                 "after": 1.191775, "reason": "test:opening"},
            ],
        }
        before_ledger = [dict(row) for row in db["ledger"]]

        with patch("store.purchase_service.load_items", return_value={}), patch(
            "store.purchase_service.resolve_item_id", return_value=None
        ), patch(
            "store.purchase_service.state_manager.atomic_update",
            side_effect=lambda mutate: mutate(db),
        ):
            result = purchase_service.purchase_physical(
                "buyer", "item", request_id="ledger-tail-mismatch-test"
            )

        self.assertEqual(result, (None, "SELLER_LEDGER_TAIL_MISMATCH"))
        self.assertEqual(db["users"]["buyer"]["wallet"]["credits"], 1.0)
        self.assertEqual(db["users"]["seller"]["wallet"]["credits"], 6.191775)
        self.assertEqual(db["products"]["item"]["inventory"], 1)
        self.assertEqual(db["ledger"], before_ledger)
        self.assertNotIn("purchase:ledger-tail-mismatch-test", db["purchases"])

    def test_physical_sale_keeps_buyer_and_seller_ledger_tails_contiguous(self):
        db = {
            "users": {
                "buyer": {"wallet": {"credits": 1.0}},
                "seller": {"wallet": {"credits": 2.0}},
            },
            "products": {
                "item": {
                    "type": "physical", "seller_uid": "seller",
                    "price": 1.0, "inventory": 1,
                }
            },
            "purchases": {},
            "ledger": [
                {"uid": "buyer", "before": 2.0, "amount": -1.0,
                 "after": 1.0, "reason": "test:opening"},
                {"uid": "seller", "before": 1.0, "amount": 1.0,
                 "after": 2.0, "reason": "test:opening"},
            ],
        }

        with patch("store.purchase_service.load_items", return_value={}), patch(
            "store.purchase_service.resolve_item_id", return_value=None
        ), patch(
            "store.purchase_service.state_manager.atomic_update",
            side_effect=lambda mutate: mutate(db),
        ):
            result, error = purchase_service.purchase_physical(
                "buyer", "item", request_id="ledger-tail-match-test"
            )

        self.assertIsNone(error)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(db["users"]["buyer"]["wallet"]["credits"], 0.0)
        self.assertAlmostEqual(db["users"]["seller"]["wallet"]["credits"], 2.9)
        self.assertEqual(db["products"]["item"]["inventory"], 0)
        self.assertTrue(audit_account_ledger(db, "buyer")["current_balance_matches_tail"])
        self.assertTrue(audit_account_ledger(db, "seller")["current_balance_matches_tail"])

if __name__ == "__main__":
    unittest.main()
