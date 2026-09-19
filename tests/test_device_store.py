import json
import tempfile
import unittest
from pathlib import Path

from core.device_store import DeviceStore


class DeviceStoreTests(unittest.TestCase):
    def test_create_get_and_list_for_user(self):
        with tempfile.TemporaryDirectory() as td:
            store = DeviceStore(Path(td) / "devices.json")
            created = store.create(
                "DEV_TEST_1",
                {"name": "Test", "owner": "123", "status": "offline"},
            )
            self.assertEqual(created["device_id"], "DEV_TEST_1")
            self.assertEqual(created["owner_id"], "123")
            self.assertEqual(store.get("DEV_TEST_1")["owner_id"], "123")
            self.assertIn("DEV_TEST_1", store.list_for_user("123"))

    def test_update_and_heartbeat_are_atomic_and_persistent(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "devices.json"
            store = DeviceStore(path)
            store.create("DEV_TEST_2", {"name": "Test", "owner_id": "456"})
            store.update("DEV_TEST_2", {"capabilities": ["protection"]})
            updated = store.heartbeat("DEV_TEST_2")
            self.assertEqual(updated["status"], "online")
            self.assertIsNotNone(updated["last_seen"])

            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["devices"]["DEV_TEST_2"]["owner_id"], "456")
            self.assertEqual(raw["devices"]["DEV_TEST_2"]["status"], "online")

    def test_duplicate_create_and_missing_update_fail(self):
        with tempfile.TemporaryDirectory() as td:
            store = DeviceStore(Path(td) / "devices.json")
            store.create("DEV_TEST_3", {"name": "Test", "owner_id": "789"})
            with self.assertRaises(ValueError):
                store.create("DEV_TEST_3", {"name": "Duplicate"})
            with self.assertRaises(KeyError):
                store.update("MISSING", {"status": "online"})


if __name__ == "__main__":
    unittest.main()
