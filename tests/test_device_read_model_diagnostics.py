import json
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core import device_read_model


class DeviceReadModelDiagnosticsTests(unittest.TestCase):
    def test_fresh_signed_diagnostics_are_available_to_owner_status_view(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "devices.json"
            now = datetime.now(timezone.utc).isoformat()
            snapshot = {
                "version": 1,
                "docker": {
                    "daemon": "UP",
                    "container_count": 22,
                    "running_count": 20,
                    "restarting_names": [],
                },
                "postgres": "UP",
                "redis": "UP",
                "git": {"branch": "main", "commit": "abcdef1", "dirty": False, "dirty_files": 0},
                "compose": {
                    "utf8": "PASS",
                    "bad_byte_97_count": 0,
                    "root_env_present": True,
                    "claude_env_present": False,
                },
                "bots": {
                    "slh-ton-mnh": "UP",
                    "slh-nifti": "UNKNOWN",
                    "slh-crazy-panel": "UP",
                },
            }
            path.write_text(json.dumps({
                "devices": {
                    "PC_Osif2": {
                        "name": "PC_Osif2",
                        "status": "online",
                        "last_heartbeat": now,
                        "diagnostics": snapshot,
                        "diagnostics_received_at": now,
                    }
                }
            }), encoding="utf-8")
            with patch.object(device_read_model, "DEVICES_PATH", path):
                result = device_read_model.get_device_status("PC_Osif2")
            self.assertEqual(result["status"], "online")
            self.assertEqual(result["diagnostics"], snapshot)
            self.assertLessEqual(result["diagnostics_age_seconds"], 2)

    def test_stale_diagnostics_are_hidden_even_when_heartbeat_is_live(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "devices.json"
            now = time.time()
            fresh = datetime.fromtimestamp(now, timezone.utc).isoformat()
            stale = datetime.fromtimestamp(now - 121, timezone.utc).isoformat()
            path.write_text(json.dumps({
                "devices": {
                    "PC_Osif2": {
                        "name": "PC_Osif2",
                        "last_heartbeat": fresh,
                        "diagnostics": {"version": 1, "docker": {"daemon": "UP"}},
                        "diagnostics_received_at": stale,
                    }
                }
            }), encoding="utf-8")
            with patch.object(device_read_model, "DEVICES_PATH", path):
                result = device_read_model.get_device_status("PC_Osif2", ttl_seconds=120)
            self.assertEqual(result["status"], "online")
            self.assertIsNone(result["diagnostics"])
            self.assertGreater(result["diagnostics_age_seconds"], 120)


if __name__ == "__main__":
    unittest.main()
