import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from store.grant_engine import apply_grant


class StoreCatalogFulfillmentTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.items = json.loads(
            (self.repo_root / "store" / "items.json").read_text(encoding="utf-8")
        )

    def test_catalog_has_real_fulfillment_grants(self):
        expected = {
            "course_bitcoin_101": ("course", "bitcoin_mastery"),
            "course_ethereum": ("course", "ethereum"),
            "course_slh_vs_eth_sol": ("course", "slh_vs_eth_sol"),
            "emoji_bitcoin": ("digital", "emoji_bitcoin"),
            "emoji_slh": ("digital", "emoji_slh"),
            "emoji_vip": ("digital", "emoji_vip"),
            "agent_os": ("plugin", "agent_os"),
            "trade_pro": ("permission", "trade_pro"),
            "esp32_pro": ("hardware", "esp32_pro"),
            "esp32_standard": ("hardware", "esp32_standard"),
        }
        self.assertEqual(set(self.items), set(expected))
        for item_id, (grant_type, value) in expected.items():
            item = self.items[item_id]
            self.assertEqual(item["grant"], {grant_type: value})

    def test_course_grant_enrolls_in_academy(self):
        with patch("store.grant_engine.profile_manager.get_user", return_value={}),              patch("core.academy_manager.start_course", return_value=True) as start_course:
            result = apply_grant("100", {"course": "bitcoin_mastery"}, purchase_id="p1")

        self.assertTrue(result["ok"])
        self.assertTrue(result["academy_enrolled"])
        start_course.assert_called_once_with("100", "bitcoin_mastery")

    def test_digital_grant_enters_user_inventory(self):
        user = {"inventory": {"digital": []}}
        with patch("store.grant_engine.profile_manager.get_user", return_value=user),              patch("store.grant_engine.profile_manager.update_user") as update_user:
            result = apply_grant("100", {"digital": "emoji_slh"}, purchase_id="p2")

        self.assertTrue(result["ok"])
        self.assertEqual(result["value"], "emoji_slh")
        update_user.assert_called_once_with(
            "100", {"inventory": {"digital": ["emoji_slh"]}}
        )

    def test_plugin_grant_installs_and_entitles_plugin(self):
        user = {"inventory": {"plugins": []}}
        with patch("store.grant_engine.profile_manager.get_user", return_value=user),              patch("store.grant_engine.profile_manager.update_user") as update_user,              patch("plugins_store.install_plugin", return_value="✅ installed") as install:
            result = apply_grant("100", {"plugin": "agent_os"}, purchase_id="p3")

        self.assertTrue(result["ok"])
        self.assertEqual(result["value"], "agent_os")
        install.assert_called_once_with("agent_os")
        update_user.assert_called_once_with(
            "100", {"inventory": {"plugins": ["agent_os"]}}
        )

    def test_hardware_grant_creates_device_and_license(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "state").mkdir()
            (root / "state" / "devices.json").write_text(
                json.dumps({"devices": {}}), encoding="utf-8"
            )
            (root / "state" / "db.json").write_text(
                json.dumps({}), encoding="utf-8"
            )

            license_payload = {
                "license_id": "test-license",
                "device_id": "ESP_PURCHASE_p4",
                "owner_id": "100",
            }
            with patch("store.grant_engine.issue_license", return_value={"ok": True, "license": license_payload}),                  patch("store.grant_engine.profile_manager.get_user", return_value={}):
                import os
                old = os.getcwd()
                os.chdir(tmp)
                try:
                    result = apply_grant(
                        "100",
                        {"hardware": "esp32_pro"},
                        purchase_id="p4",
                    )
                finally:
                    os.chdir(old)

            self.assertTrue(result["ok"])
            self.assertEqual(result["device_id"], "ESP_PURCHASE_p4")
            devices = json.loads(
                (root / "state" / "devices.json").read_text(encoding="utf-8")
            )
            self.assertEqual(devices["devices"]["ESP_PURCHASE_p4"]["owner"], "100")
            db = json.loads((root / "state" / "db.json").read_text(encoding="utf-8"))
            self.assertIn("ESP_PURCHASE_p4", db["device_wallets"])
            self.assertEqual(db["device_agent_map"]["ESP_PURCHASE_p4"], "7")


if __name__ == "__main__":
    unittest.main()
