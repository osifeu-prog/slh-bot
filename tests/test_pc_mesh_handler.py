import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from handlers import pc_mesh_handler


class PcMeshHandlerTests(unittest.TestCase):
    def test_kind_separates_pc_and_esp(self):
        self.assertEqual(pc_mesh_handler._kind({"type": "pc", "device_id": "PC_OSIF2"}), "PC")
        self.assertEqual(pc_mesh_handler._kind({"type": "esp32", "device_id": "ESP_01"}), "ESP")
        self.assertEqual(pc_mesh_handler._kind({"device_id": "PC_OSIF3"}), "PC")

    def test_owner_only_pc_and_mesh(self):
        bot = mock.Mock()
        handlers = []
        bot.message_handler.side_effect = lambda **kwargs: (lambda fn: handlers.append((kwargs["commands"], fn)) or fn)
        pc_mesh_handler.register(bot)
        self.assertTrue(any("pc" in commands for commands, _ in handlers))
        self.assertTrue(any("mesh" in commands for commands, _ in handlers))

    def test_devices_are_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "devices.json"
            path.write_text(json.dumps({"devices": {
                "PC_OSIF2": {"type": "pc", "device_id": "PC_OSIF2", "status": "online"},
                "ESP_01": {"type": "esp32", "device_id": "ESP_01", "status": "offline"},
            }}), encoding="utf-8")
            with mock.patch.object(pc_mesh_handler, "DEVICES_PATH", path):
                self.assertEqual(len(pc_mesh_handler._devices()), 2)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["devices"]["PC_OSIF2"]["status"], "online")


if __name__ == "__main__":
    unittest.main()
