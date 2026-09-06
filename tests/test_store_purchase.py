import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import state_manager
from store import purchase_service


class StorePurchaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_file = self.root / "db.json"
        self.lock_file = self.root / "db.json.lock"
        self.db_file.write_text(
            json.dumps({
                "users": {"1": {"wallet": {"credits": 2000}}},
                "products": {"esp32_standard": {"type": "hardware", "inventory": 2}},
            }),
            encoding="utf-8",
        )
        state_manager.DB_FILE = str(self.db_file)
        state_manager._LOCK_PATH = str(self.lock_file)
        purchase_service.LEDGER_FILE = str(self.root / "rewards_ledger.json")

    def tearDown(self):
        self.tmp.cleanup()

    def _items(self, price=100, kind="digital"):
        return {
            "item": {
                "name": "Test Item",
                "price": price,
                "type": kind,
                "grant": {"digital": "test"},
            }
        }

    def test_new_purchase_charges_once_and_fulfills(self):
        with patch.object(purchase_service, "load_items", return_value=self._items()), \
             patch.object(purchase_service, "apply_grant", return_value={"ok": True, "type": "digital", "value": "test"}) as grant:
            ok, result = purchase_service.purchase(1, "item", "req-1")
        self.assertTrue(ok)
        self.assertEqual(result["status"], "SUCCESS")
        grant.assert_called_once()
        db = state_manager.load_db()
        self.assertEqual(db["users"]["1"]["wallet"]["credits"], 1900)
        self.assertEqual(len(db["ledger"]), 1)
        self.assertEqual(db["purchases"]["purchase:req-1"]["status"], "FULFILLED")

    def test_same_request_id_does_not_charge_twice(self):
        with patch.object(purchase_service, "load_items", return_value=self._items()), \
             patch.object(purchase_service, "apply_grant", return_value={"ok": True, "type": "digital", "value": "test"}) as grant:
            purchase_service.purchase(1, "item", "req-1")
            ok, result = purchase_service.purchase(1, "item", "req-1")
        self.assertTrue(ok)
        self.assertEqual(result["status"], "ALREADY_COMPLETED")
        self.assertEqual(grant.call_count, 1)
        db = state_manager.load_db()
        self.assertEqual(db["users"]["1"]["wallet"]["credits"], 1900)
        self.assertEqual(len(db["ledger"]), 1)

    def test_different_request_ids_are_distinct_purchases(self):
        with patch.object(purchase_service, "load_items", return_value=self._items()), \
             patch.object(purchase_service, "apply_grant", return_value={"ok": True, "type": "digital", "value": "test"}):
            purchase_service.purchase(1, "item", "req-1")
            purchase_service.purchase(1, "item", "req-2")
        db = state_manager.load_db()
        self.assertEqual(db["users"]["1"]["wallet"]["credits"], 1800)
        self.assertEqual(len(db["purchases"]), 2)

    def test_insufficient_balance_does_not_charge(self):
        with patch.object(purchase_service, "load_items", return_value=self._items(price=3000)), \
             patch.object(purchase_service, "apply_grant") as grant:
            ok, result = purchase_service.purchase(1, "item", "req-1")
        self.assertFalse(ok)
        self.assertEqual(result, "NOT_ENOUGH_SLH")
        grant.assert_not_called()
        db = state_manager.load_db()
        self.assertEqual(db["users"]["1"]["wallet"]["credits"], 2000)
        self.assertEqual(db["purchases"]["purchase:req-1"]["status"], "REJECTED")

    def test_fulfillment_failure_is_recoverable_without_second_charge(self):
        with patch.object(purchase_service, "load_items", return_value=self._items()), \
             patch.object(purchase_service, "apply_grant", side_effect=[RuntimeError("boom"), {"ok": True, "type": "digital", "value": "test"}]) as grant:
            ok, result = purchase_service.purchase(1, "item", "req-1")
            self.assertFalse(ok)
            self.assertEqual(result, "RECOVERABLE")
            ok, result = purchase_service.purchase(1, "item", "req-1")
        self.assertTrue(ok)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(grant.call_count, 2)
        db = state_manager.load_db()
        self.assertEqual(db["users"]["1"]["wallet"]["credits"], 1900)
        self.assertEqual(len(db["ledger"]), 1)

    def test_inventory_unavailable_rejects_before_debit(self):
        self.db_file.write_text(
            json.dumps({
                "users": {"1": {"wallet": {"credits": 2000}}},
                "products": {"esp32_standard": {"type": "hardware", "inventory": 0}},
            }),
            encoding="utf-8",
        )
        item = {"item": {"name": "HW", "price": 444, "type": "hardware", "grant": {"hardware": "esp32_standard"}}}
        with patch.object(purchase_service, "load_items", return_value=item), patch.object(purchase_service, "apply_grant") as grant:
            ok, result = purchase_service.purchase(1, "item", "req-hw")
        self.assertFalse(ok)
        self.assertEqual(result, "OUT_OF_STOCK")
        grant.assert_not_called()
        db = state_manager.load_db()
        self.assertEqual(db["users"]["1"]["wallet"]["credits"], 2000)

    def test_negative_price_is_rejected(self):
        item = {"item": {"name": "Bad", "price": -1, "type": "digital", "grant": {"digital": "bad"}}}
        with patch.object(purchase_service, "load_items", return_value=item), patch.object(purchase_service, "apply_grant") as grant:
            ok, result = purchase_service.purchase(1, "item", "req-bad")
        self.assertFalse(ok)
        self.assertEqual(result, "NEGATIVE_PRICE")
        grant.assert_not_called()

    def test_hardware_purchase_reserves_inventory_once(self):
        item = {"item": {"name": "HW", "price": 444, "type": "hardware", "grant": {"hardware": "esp32_standard"}}}
        fulfillment = {"ok": True, "type": "hardware", "device_id": "ESP_PURCHASE_purchase_req-hw", "license": {"license_id": "lic-1"}}
        with patch.object(purchase_service, "load_items", return_value=item), patch.object(purchase_service, "apply_grant", return_value=fulfillment):
            purchase_service.purchase(1, "item", "req-hw")
            purchase_service.purchase(1, "item", "req-hw")
        db = state_manager.load_db()
        self.assertEqual(db["products"]["esp32_standard"]["inventory"], 1)
        self.assertEqual(db["users"]["1"]["wallet"]["credits"], 1556)


if __name__ == "__main__":
    unittest.main()
