import copy
import unittest
from unittest.mock import patch

from store import purchase_service


def _db(*, frozen_buyer=False, frozen_seller=False):
    buyer = {"wallet": {"credits": 100.0}}
    seller = {"wallet": {"credits": 20.0}}
    if frozen_buyer:
        buyer["frozen"] = True
    if frozen_seller:
        seller["frozen"] = True
    return {
        "users": {
            "buyer": buyer,
            "seller": seller,
            "SLH_TREASURY": {"wallet": {"credits": 0.0}},
        },
        "products": {
            "physical-item": {
                "type": "physical",
                "name": "Test item",
                "price": 25.0,
                "seller_uid": "seller",
                "inventory": 2,
            },
            "hardware-item": {"inventory": 2},
        },
        "ledger": [],
        "purchases": {},
    }


class FrozenStorePurchaseTests(unittest.TestCase):
    def _purchase_physical(self, db, request_id="physical-request"):
        with (
            patch.object(
                purchase_service.state_manager,
                "atomic_update",
                side_effect=lambda mutate: mutate(db),
            ),
            patch.object(purchase_service, "load_items", return_value={}),
            patch.object(purchase_service, "resolve_item_id", return_value=None),
        ):
            return purchase_service.purchase_physical(
                "buyer", "physical-item", request_id=request_id
            )

    def test_frozen_buyer_cannot_buy_physical_item(self):
        db = _db(frozen_buyer=True)
        before = copy.deepcopy(db)

        result, error = self._purchase_physical(db)

        self.assertIsNone(result)
        self.assertEqual(error, "ACCOUNT_FROZEN")
        self.assertEqual(db, before)

    def test_frozen_seller_listing_cannot_be_purchased(self):
        db = _db(frozen_seller=True)
        before = copy.deepcopy(db)

        result, error = self._purchase_physical(db)

        self.assertIsNone(result)
        self.assertEqual(error, "ACCOUNT_FROZEN")
        self.assertEqual(db, before)

    def test_frozen_buyer_cannot_create_new_store_purchase_or_reserve_inventory(self):
        db = _db(frozen_buyer=True)
        before = copy.deepcopy(db)
        item = {
            "type": "hardware",
            "name": "Test hardware",
            "price": 10.0,
            "grant": {"hardware": "test-device"},
        }

        with patch.object(
            purchase_service.state_manager,
            "atomic_update",
            side_effect=lambda mutate: mutate(db),
        ):
            result, error = purchase_service._get_or_create_purchase(
                "buyer", "hardware-item", "hardware-request", item
            )

        self.assertIsNone(result)
        self.assertEqual(error, "ACCOUNT_FROZEN")
        self.assertEqual(db, before)

    def test_completed_physical_purchase_retry_remains_idempotent_when_frozen(self):
        db = _db(frozen_buyer=True, frozen_seller=True)
        db["purchases"]["purchase:physical-request"] = {
            "purchase_id": "purchase:physical-request",
            "request_id": "physical-request",
            "uid": "buyer",
            "item_id": "physical-item",
            "item_name": "Test item",
            "price": 25.0,
            "seller_uid": "seller",
            "status": "PAID",
        }
        before = copy.deepcopy(db)

        result, error = self._purchase_physical(db)

        self.assertIsNone(error)
        self.assertEqual(result["status"], "ALREADY_COMPLETED")
        self.assertEqual(db, before)


if __name__ == "__main__":
    unittest.main()
