import os
import unittest
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class MCPBridgeTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "SLH_MCP_BRIDGE_TOKEN": os.environ.get("SLH_MCP_BRIDGE_TOKEN"),
            "SLH_MCP_PRINCIPAL_ID": os.environ.get("SLH_MCP_PRINCIPAL_ID"),
        }

    def tearDown(self):
        for key, value in self.env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _client(self):
        import webapp
        webapp.app.config.update(TESTING=True)
        return webapp.app.test_client()

    def test_bridge_requires_secret(self):
        import webapp
        os.environ.pop("SLH_MCP_BRIDGE_TOKEN", None)
        with self._client() as client:
            response = client.get(
                "/api/internal/mcp/agents",
                headers={"X-SLH-MCP-Principal": str(OWNER_TELEGRAM_ID)},
            )
        self.assertEqual(response.status_code, 503)

    def test_bridge_rejects_wrong_secret(self):
        os.environ["SLH_MCP_BRIDGE_TOKEN"] = "expected"
        with self._client() as client:
            response = client.get(
                "/api/internal/mcp/agents",
                headers={
                    "X-SLH-MCP-Key": "wrong",
                    "X-SLH-MCP-Principal": str(OWNER_TELEGRAM_ID),
                },
            )
        self.assertEqual(response.status_code, 403)

    def test_agents_route_uses_canonical_visibility(self):
        import webapp

        os.environ["SLH_MCP_BRIDGE_TOKEN"] = "expected"
        with patch("webapp.list_agents", return_value={
            "1": {"id": "1", "name": "alpha", "owner_id": str(OWNER_TELEGRAM_ID), "state": "idle"},
            "2": {"id": "2", "name": "other", "owner_id": "999", "state": "idle"},
        }), patch(
            "webapp.get_visible_agents",
            return_value={"1": {"id": "1", "name": "alpha", "owner_id": str(OWNER_TELEGRAM_ID), "state": "idle"}},
        ) as visible:
            with self._client() as client:
                response = client.get(
                    "/api/internal/mcp/agents",
                    headers={
                        "X-SLH-MCP-Key": "expected",
                        "X-SLH-MCP-Principal": str(OWNER_TELEGRAM_ID),
                    },
                )
        self.assertEqual(response.status_code, 200)
        visible.assert_called_once()
        self.assertEqual(response.get_json(), {
            "agents": [{"id":"1","name":"alpha","state":"idle"}],
        })

    def test_execute_requires_agent_permission_and_delegates(self):
        import webapp

        os.environ["SLH_MCP_BRIDGE_TOKEN"] = "expected"
        with patch("webapp.list_agents", return_value={"1": {"id":"1","owner_id":str(OWNER_TELEGRAM_ID)}}),              patch("webapp.get_visible_agents", return_value={"1": {"id":"1","owner_id":str(OWNER_TELEGRAM_ID)}}),              patch("webapp.get_agent", return_value=("1", {"id":"1","owner_id":str(OWNER_TELEGRAM_ID)})),              patch("webapp.execute_agent", return_value={"status":"ok"}) as execute:
            with self._client() as client:
                response = client.post(
                    "/api/internal/mcp/agents/1/execute",
                    headers={
                        "X-SLH-MCP-Key": "expected",
                        "X-SLH-MCP-Principal": str(OWNER_TELEGRAM_ID),
                    },
                    json={"command":"ping"},
                )
        self.assertEqual(response.status_code, 200)
        execute.assert_called_once_with("1", "ping", source="mcp")
        self.assertEqual(response.get_json(), {"status":"ok"})

    def test_bridge_never_returns_user_wallet(self):
        import webapp
        os.environ["SLH_MCP_BRIDGE_TOKEN"] = "expected"
        row = {
            "id": "1", "name": "alpha", "owner_id": str(OWNER_TELEGRAM_ID),
            "state": "idle", "wallet": {"credits": 123},
        }
        with patch("webapp.list_agents", return_value={"1": row}),              patch("webapp.get_visible_agents", return_value={"1": row}):
            with self._client() as client:
                response = client.get(
                    "/api/internal/mcp/agents",
                    headers={
                        "X-SLH-MCP-Key": "expected",
                        "X-SLH-MCP-Principal": str(OWNER_TELEGRAM_ID),
                    },
                )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("wallet", response.get_json()["agents"][0])


if __name__ == "__main__":
    unittest.main()
