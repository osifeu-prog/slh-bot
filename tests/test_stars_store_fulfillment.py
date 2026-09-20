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
        self.repo_root = Path(__file__).resolve().parents[1]
        self.catalog = json.loads(
            (self.repo_root / "store" / "items.json").read_text(encoding="utf-8")
        )
        self.patches = [
            patch("store.stars_purchase_service.state_manager.load_db", side_effect=self.load_db),
            patch("store.stars_purchase_service.state_manager.atomic_update", side_effect=self.atomic_update),
            patch("store.stars_purchase_service.load_items", return_value={
                "role_vip": {
                    "name": "VIP",
                    "price": 500,
                    "price_stars": 500,
                    "type": "role",
                    "grant": {"permission": "vip_access"},
                }
            }),
            patch(
                "store.stars_purchase_service.apply_grant",
                return_value={"ok": True, "type": "permission", "value": "vip_access"},
            ),
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

    def test_duplicate_charge_is_idempotent_and_grants_once(self):
        with patch(
            "store.stars_purchase_service.apply_grant",
            return_value={"ok": True, "type": "permission", "value": "vip_access"},
        ) as grant:
            first = purchase_item_with_stars("100", "role_vip", 500, "charge-1")
            second = purchase_item_with_stars("100", "role_vip", 500, "charge-1")

        self.assertEqual(first["status"], "SUCCESS")
        self.assertEqual(second["status"], "DUPLICATE")
        self.assertEqual(grant.call_count, 1)
        self.assertEqual(self.load_db()["revenue"]["stars_gross"], 500)

    def test_fulfilled_replay_reconciles_missing_revenue_ledger(self):
        first = purchase_item_with_stars("100", "role_vip", 500, "charge-revenue-recovery")
        self.assertEqual(first["status"], "SUCCESS")

        db = self.load_db()
        db.pop("revenue_ledger", None)
        self.db_path.write_text(json.dumps(db), encoding="utf-8")

        second = purchase_item_with_stars("100", "role_vip", 500, "charge-revenue-recovery")
        self.assertEqual(second["status"], "DUPLICATE")

        repaired = self.load_db()
        self.assertEqual(len(repaired["revenue_ledger"]), 1)
        self.assertEqual(repaired["revenue_ledger"][0]["reference"], "charge-revenue-recovery")

    def test_real_catalog_course_purchase_uses_real_grant(self):
        item = self.catalog["course_bitcoin_101"]
        self.assertEqual(item["price_stars"], 299)

        with patch("store.stars_purchase_service.load_items", return_value=self.catalog),              patch(
                 "store.stars_purchase_service.apply_grant",
                 return_value={
                     "ok": True,
                     "type": "course",
                     "value": "bitcoin_mastery",
                     "academy_enrolled": True,
                 },
             ) as grant:
            result = purchase_item_with_stars(
                "100", "course_bitcoin_101", 299, "real-course-charge"
            )

        self.assertEqual(result["status"], "SUCCESS")
        grant.assert_called_once_with(
            "100", {"course": "bitcoin_mastery"}, purchase_id="stars:real-course-charge"
        )

    def test_real_catalog_plugin_purchase_uses_real_grant(self):
        item = self.catalog["agent_os"]
        self.assertEqual(item["price_stars"], 199)

        with patch("store.stars_purchase_service.load_items", return_value=self.catalog),              patch(
                 "store.stars_purchase_service.apply_grant",
                 return_value={
                     "ok": True,
                     "type": "digital",
                     "value": "emoji_slh",
                 },
             ) as grant:
            result = purchase_item_with_stars(
                "100", "agent_os", 199, "real-plugin-charge"
            )

        self.assertEqual(result["status"], "SUCCESS")
        grant.assert_called_once_with(
            "100", {"plugin": "agent_os"}, purchase_id="stars:real-plugin-charge"
        )

    def test_fulfillment_failure_is_recoverable_and_retry_can_fulfill(self):
        with patch(
            "store.stars_purchase_service.apply_grant",
            side_effect=[
                RuntimeError("temporary failure"),
                {"ok": True, "type": "permission", "value": "vip_access"},
            ],
        ) as grant:
            first = purchase_item_with_stars("100", "role_vip", 500, "charge-retry")
            second = purchase_item_with_stars("100", "role_vip", 500, "charge-retry")

        self.assertEqual(first["status"], "RECOVERABLE")
        self.assertEqual(second["status"], "SUCCESS")
        self.assertEqual(grant.call_count, 2)
        db = self.load_db()
        self.assertEqual(db["star_item_orders"]["stars:charge-retry"]["status"], "FULFILLED")
        self.assertEqual(db["revenue"]["stars_gross"], 500)
        self.assertEqual(db["revenue"]["orders"], 1)


if __name__ == "__main__":
    unittest.main()
