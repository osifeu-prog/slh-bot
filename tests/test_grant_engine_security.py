import json
import tempfile
import unittest
from pathlib import Path

import state_manager
from core.developer_lab import can_propose_path
from store.grant_engine import _canonical_uid


class TestGrantEngineSecurity(unittest.TestCase):
    def test_canonical_uid_accepts_numeric_id_and_rejects_opaque_value(self):
        self.assertEqual(_canonical_uid("123456789"), "123456789")
        self.assertEqual(_canonical_uid(123456789), "123456789")
        with self.assertRaises(ValueError):
            _canonical_uid("owner")

    def test_atomic_json_update_replaces_complete_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "devices.json"

            def mutate(data):
                data.setdefault("devices", {})["d1"] = {"owner": "123456789"}

            state_manager.atomic_json_update(str(path), mutate, default={"devices": {}})

            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["devices"]["d1"]["owner"], "123456789")
            self.assertFalse(list(Path(tmp).glob("*.tmp")))

    def test_developer_lab_blocks_state_and_store_writes(self):
        self.assertFalse(can_propose_path("store/grant_engine.py"))
        self.assertFalse(can_propose_path("state/db.json"))
        self.assertFalse(can_propose_path("core/authority.py"))
        self.assertTrue(can_propose_path("tests/test_grant_engine_security.py"))


if __name__ == "__main__":
    unittest.main()
