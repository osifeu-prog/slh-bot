import unittest
from unittest.mock import patch

from store import purchase_service


class StorePurchaseSagaTests(unittest.TestCase):
    def setUp(self):
        self.db = {
            "users": {"u1": {"wallet": {"credits": 100}}},
            "products": {"hw": {"type": "hardware", "inventory": 1}},
        }
        self.items = {
            "digital": {"name": "Digital", "price": 25, "type": "digital", "grant": {"digital": "badge"}},
            "hw": {"name": "Hardware", "price": 40, "type": "hardware", "grant": {"hardware": "hw"}},
            "free": {"name": "Free", "price": 0, "type": "course", "grant": {"course": "intro"}},
        }

        def atomic_update(fn):
            result = fn(self.db)
            return result

        self.atomic = atomic_update

    def test_new_purchase_charges_once_and_fulfills(self):
        debits = []
        grants = []

        def spend(uid, amount, reason=None, meta=None):
            debits.append((uid, amount, meta["idempotency_key"]))
            self.db["users"][uid]["wallet"]["credits"] -= amount
            return self.db["users"][uid]["wallet"]["credits"]

        def grant(uid, grant, purchase_id=None):
            grants.append(purchase_id)
            return {"ok": True, "type": "digital", "value": "badge", "purchase_id": purchase_id}

        with patch.object(purchase_service, "load_items", return_value=self.items), \
             patch.object(purchase_service.state_manager, "atomic_update", side_effect=self.atomic), \
             patch.object(purchase_service, "get_balance", return_value=100), \
             patch.object(purchase_service, "spend", side_effect=spend), \
             patch.object(purchase_service, "apply_grant", side_effect=grant), \
             patch.object(purchase_service, "_record_compat_ledger"):
            ok, result = purchase_service.purchase("u1", "digital", "req-1")

        self.assertTrue(ok)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(len(debits), 1)
        self.assertEqual(len(grants), 1)
        self.assertEqual(self.db["purchases"]["purchase:req-1"]["status"], "FULFILLED")

    def test_same_request_id_does_not_charge_twice(self):
        debits = []

        def spend(uid, amount, reason=None, meta=None):
            debits.append(meta["idempotency_key"])
            self.db["users"][uid]["wallet"]["credits"] -= amount
            return self.db["users"][uid]["wallet"]["credits"]

        def grant(uid, grant, purchase_id=None):
            return {"ok": True, "type": "digital", "value": "badge", "purchase_id": purchase_id}

        with patch.object(purchase_service, "load_items", return_value=self.items), \
             patch.object(purchase_service.state_manager, "atomic_update", side_effect=self.atomic), \
             patch.object(purchase_service, "get_balance", return_value=100), \
             patch.object(purchase_service, "spend", side_effect=spend), \
             patch.object(purchase_service, "apply_grant", side_effect=grant), \
             patch.object(purchase_service, "_record_compat_ledger"):
            first = purchase_service.purchase("u1", "digital", "req-1")
            second = purchase_service.purchase("u1", "digital", "req-1")

        self.assertTrue(first[0])
        self.assertTrue(second[0])
        self.assertEqual(second[1]["status"], "ALREADY_COMPLETED")
        self.assertEqual(len(debits), 1)

    def test_different_request_ids_are_distinct_purchases(self):
        debits = []

        def spend(uid, amount, reason=None, meta=None):
            debits.append(meta["purchase_id"])
            self.db["users"][uid]["wallet"]["credits"] -= amount
            return self.db["users"][uid]["wallet"]["credits"]

        with patch.object(purchase_service, "load_items", return_value=self.items), \
             patch.object(purchase_service.state_manager, "atomic_update", side_effect=self.atomic), \
             patch.object(purchase_service, "get_balance", return_value=100), \
             patch.object(purchase_service, "spend", side_effect=spend), \
             patch.object(purchase_service, "apply_grant", return_value={"ok": True, "type": "digital", "value": "badge"}), \
             patch.object(purchase_service, "_record_compat_ledger"):
            purchase_service.purchase("u1", "digital", "req-1")
            purchase_service.purchase("u1", "digital", "req-2")

        self.assertEqual(len(debits), 2)
        self.assertNotEqual(debits[0], debits[1])

    def test_fulfillment_failure_becomes_recoverable_without_second_charge(self):
        debits = []
        grant_calls = []

        def spend(uid, amount, reason=None, meta=None):
            debits.append(meta["purchase_id"])
            self.db["users"][uid]["wallet"]["credits"] -= amount
            return self.db["users"][uid]["wallet"]["credits"]

        def grant(uid, grant, purchase_id=None):
            grant_calls.append(purchase_id)
            if len(grant_calls) == 1:
                raise RuntimeError("temporary")
            return {"ok": True, "type": "digital", "value": "badge", "purchase_id": purchase_id}

        with patch.object(purchase_service, "load_items", return_value=self.items), \
             patch.object(purchase_service.state_manager, "atomic_update", side_effect=self.atomic), \
             patch.object(purchase_service, "get_balance", return_value=100), \
             patch.object(purchase_service, "spend", side_effect=spend), \
             patch.object(purchase_service, "apply_grant", side_effect=grant), \
             patch.object(purchase_service, "_record_compat_ledger"):
            first = purchase_service.purchase("u1", "digital", "req-1")
            second = purchase_service.purchase("u1", "digital", "req-1")

        self.assertFalse(first[0])
        self.assertEqual(first[1], "RECOVERABLE")
        self.assertTrue(second[0])
        self.assertEqual(second[1]["status"], "SUCCESS")
        self.assertEqual(len(debits), 1)
        self.assertEqual(len(grant_calls), 2)

    def test_out_of_stock_hardware_is_rejected_before_charge(self):
        self.db["products"]["hw"]["inventory"] = 0
        debits = []

        with patch.object(purchase_service, "load_items", return_value=self.items), \
             patch.object(purchase_service.state_manager, "atomic_update", side_effect=self.atomic), \
             patch.object(purchase_service, "get_balance", return_value=100), \
             patch.object(purchase_service, "spend", side_effect=lambda *a, **k: debits.append(1)), \
             patch.object(purchase_service, "apply_grant"):
            ok, result = purchase_service.purchase("u1", "hw", "req-hw")

        self.assertFalse(ok)
        self.assertEqual(result, "OUT_OF_STOCK")
        self.assertEqual(debits, [])
        self.assertEqual(self.db["products"]["hw"]["inventory"], 0)

    def test_negative_price_is_rejected(self):
        items = dict(self.items)
        items["bad"] = {"name": "Bad", "price": -1, "grant": {"digital": "bad"}}
        with patch.object(purchase_service, "load_items", return_value=items), \
             patch.object(purchase_service.state_manager, "atomic_update", side_effect=self.atomic), \
             patch.object(purchase_service, "spend") as spend:
            ok, result = purchase_service.purchase("u1", "bad", "req-bad")

        self.assertFalse(ok)
        self.assertEqual(result, "NEGATIVE_PRICE")
        spend.assert_not_called()


if __name__ == "__main__":
    unittest.main()
