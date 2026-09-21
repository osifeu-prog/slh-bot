import os
import unittest
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class MCPStandaloneBridgeTests(unittest.TestCase):
    def setUp(self):
        self._old = {
            "SLH_MCP_STANDALONE": os.environ.get("SLH_MCP_STANDALONE"),
            "SLH_CONTROL_PLANE_URL": os.environ.get("SLH_CONTROL_PLANE_URL"),
            "SLH_MCP_BRIDGE_TOKEN": os.environ.get("SLH_MCP_BRIDGE_TOKEN"),
        }
        os.environ["SLH_MCP_STANDALONE"] = "1"
        os.environ["SLH_CONTROL_PLANE_URL"] = "https://control.example"
        os.environ["SLH_MCP_BRIDGE_TOKEN"] = "bridge-test"

    def tearDown(self):
        for name, value in self._old.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_agents_list_uses_bridge(self):
        from slh_mcp.tools import agents as module
        remote = [{"id": "1", "name": "remote-agent", "state": "idle"}]
        with patch("slh_mcp.tools.agents.bridge_get_agents", return_value=remote) as bridge,              patch("slh_mcp.tools.agents.list_agents", side_effect=AssertionError("local registry used")):
            result = module.agents_list(
                type("Principal", (), {"subject": str(OWNER_TELEGRAM_ID)})()
            )
        bridge.assert_called_once_with(str(OWNER_TELEGRAM_ID))
        self.assertEqual(result, remote)

    def test_missions_list_uses_bridge(self):
        from slh_mcp.tools import missions as module
        remote = [{"id": "m1", "status": "executed", "assigned_to": "1", "reward": 10}]
        with patch("slh_mcp.tools.missions.bridge_get_missions", return_value=remote) as bridge,              patch("slh_mcp.tools.missions.MissionLifecycleService", side_effect=AssertionError("local missions used")):
            result = module.missions_list(
                type("Principal", (), {"subject": str(OWNER_TELEGRAM_ID)})()
            )
        bridge.assert_called_once_with(str(OWNER_TELEGRAM_ID))
        self.assertEqual(result[0]["id"], "m1")


if __name__ == "__main__":
    unittest.main()
