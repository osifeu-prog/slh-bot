import os
import unittest
from unittest.mock import patch

from flask import Flask

from core.identity import OWNER_TELEGRAM_ID
from core.mcp_bridge import register_mcp_bridge


class MCPBridgeTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        register_mcp_bridge(self.app)
        self.client = self.app.test_client()
        self._old = {
            "SLH_MCP_BRIDGE_TOKEN": os.environ.get("SLH_MCP_BRIDGE_TOKEN"),
        }
        os.environ["SLH_MCP_BRIDGE_TOKEN"] = "bridge-test"
        self.headers = {
            "X-SLH-MCP-Bridge-Token": "bridge-test",
            "X-SLH-MCP-Principal": str(OWNER_TELEGRAM_ID),
        }

    def tearDown(self):
        old = self._old["SLH_MCP_BRIDGE_TOKEN"]
        if old is None:
            os.environ.pop("SLH_MCP_BRIDGE_TOKEN", None)
        else:
            os.environ["SLH_MCP_BRIDGE_TOKEN"] = old

    def test_missing_bridge_token_is_rejected(self):
        response = self.client.get(
            "/api/internal/mcp/health",
            headers={"X-SLH-MCP-Principal": str(OWNER_TELEGRAM_ID)},
        )
        self.assertEqual(response.status_code, 401)

    def test_agents_is_scoped_by_canonical_authority(self):
        source = {
            "1": {
                "id": "1",
                "name": "alpha",
                "owner_id": str(OWNER_TELEGRAM_ID),
                "state": "idle",
                "inbox": ["secret"],
                "history": ["secret"],
                "permissions": ["private"],
            },
        }
        with patch("core.mcp_bridge.list_agents", return_value=source), patch(
            "core.mcp_bridge.get_visible_agents", return_value={"1": source["1"]}
        ):
            response = self.client.get("/api/internal/mcp/agents", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["agents"][0]["id"], "1")
        self.assertNotIn("inbox", data["agents"][0])
        self.assertNotIn("history", data["agents"][0])
        self.assertNotIn("permissions", data["agents"][0])
        self.assertNotIn("owner_id", data["agents"][0])

    def test_runtime_delegates_to_canonical_runtime(self):
        source = {
            "1": {
                "id": "1",
                "name": "alpha",
                "owner_id": str(OWNER_TELEGRAM_ID),
                "state": "idle",
            },
        }
        with patch("core.mcp_bridge.list_agents", return_value=source), patch(
            "core.mcp_bridge.get_visible_agents", return_value=source
        ), patch(
            "core.mcp_bridge.get_agent",
            return_value=("1", source["1"]),
        ), patch(
            "core.mcp_bridge.execute_agent",
            return_value={"type": "agent", "data": "pong"},
        ) as execute:
            response = self.client.post(
                "/api/internal/mcp/agents/1/execute",
                headers=self.headers,
                json={"command": "ping"},
            )
        self.assertEqual(response.status_code, 200)
        execute.assert_called_once_with("1", "ping", source="mcp-bridge")

    def test_missions_are_read_only(self):
        board = {
            "missions": [
                {"id": "m1", "desc": "test", "status": "open", "reward": 10},
            ]
        }
        fake = type("FakeLifecycle", (), {
            "load_state": lambda self: (board, {}),
        })
        with patch("core.mcp_bridge.MissionLifecycleService", fake):
            response = self.client.get("/api/internal/mcp/missions", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["missions"][0]["id"], "m1")


if __name__ == "__main__":
    unittest.main()
