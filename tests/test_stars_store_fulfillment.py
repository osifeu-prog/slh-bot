import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from store.stars_purchase_service import purchase_item_with_stars


class StarsStoreFulfillmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "db.json"
        self.db_path.write_text(
            json.dumps(
                {
                    "users": {"100": {"wallet": {"credits": 0}}},
                    "products": {"role_vip": {"inventory": 10}},
                }
            ),
            encoding="utf-8",
        )
        self.patches = [
            patch("store.stars_purchase_service.state_manager.load_db", side_effect=self.load_db),
            patch("store.stars_purchase_service.state_manager.atomic_update", side_effect=self.atomic_update),
            patch("store.stars_purchase_service.load_items", return_value={
                "role_vip": {
                    "name": "VIP",
                    "price": 500,
                    "type": "role",
                    "grant": {"permission": "vip_access"},
                }
            }),
            patch("store.stars_purchase_service.apply_grant", return_value={"ok": True, "type": "permission", "value": "vip_access"}),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def load_db(self):
        return json.loads(self.db_path.read_text(encoding="utf-8"))

    def atomic_update(self, fn):
        db = self.load_db()
        result = fn(db)
        self.db_path.write_text(json.dumps(db), encoding="utf-8")
        return result

    def test_successful_star_purchase_fulfills_and_records_revenue(self):
        result = purchase_item_with_stars("100", "role_vip", 500, "charge-1")

        self.assertEqual(result["status"], "SUCCESS")
        db = self.load_db()
        self.assertEqual(db["revenue"]["stars_gross"], 500)
        self.assertEqual(db["revenue"]["items"]["role_vip"]["stars"], 500)
        self.assertEqual(len(db["star_item_orders"]), 1)

    def test_duplicate_charge_is_idempotent(self):
        first = purchase_item_with_stars("100", "role_vip", 500, "charge-1")
        second = purchase_item_with_stars("100", "role_vip", 500, "charge-1")

        self.assertEqual(first["status"], "SUCCESS")
        self.assertEqual(second["status"], "DUPLICATE")
        self.assertEqual(self.load_db()["revenue"]["stars_gross"], 500)


if __name__ == "__main__":
    unittest.main()
