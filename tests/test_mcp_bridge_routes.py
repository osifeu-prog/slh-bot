import os
import unittest
from unittest.mock import patch

from flask import Flask


class MCPBridgeRouteTests(unittest.TestCase):
    def setUp(self):
        from core.mcp_bridge_routes import register_mcp_bridge_routes

        self.app = Flask(__name__)
        register_mcp_bridge_routes(self.app)
        self.client = self.app.test_client()

        self.env = {
            "SLH_MCP_BRIDGE_TOKEN": os.environ.get("SLH_MCP_BRIDGE_TOKEN"),
            "SLH_MCP_BRIDGE_PRINCIPAL_ID": os.environ.get("SLH_MCP_BRIDGE_PRINCIPAL_ID"),
            "SLH_MCP_PRINCIPAL_ID": os.environ.get("SLH_MCP_PRINCIPAL_ID"),
        }
        os.environ["SLH_MCP_BRIDGE_TOKEN"] = "bridge-test"
        os.environ["SLH_MCP_BRIDGE_PRINCIPAL_ID"] = "owner"

    def tearDown(self):
        for key, value in self.env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_missing_auth_is_rejected(self):
        response = self.client.get("/internal/mcp/v1/agents")
        self.assertEqual(response.status_code, 401)

    def test_client_cannot_override_configured_principal(self):
        source = {
            "1": {"id":"1","name":"A","owner_id":"owner","state":"idle"},
        }
        with patch(
            "core.mcp_bridge_routes.list_agents", return_value=source
        ), patch(
            "core.mcp_bridge_routes.get_visible_agents",
            return_value=source,
        ) as visible, patch(
            "core.mcp_bridge_routes.has_permission", return_value=True
        ):
            response = self.client.get(
                "/internal/mcp/v1/agents",
                headers={
                    "Authorization": "Bearer bridge-test",
                    "X-SLH-MCP-Subject": "attacker",
                },
            )

        self.assertEqual(response.status_code, 200)
        visible.assert_called_once_with("owner", source)

    def test_agents_uses_canonical_visibility(self):
        source = {
            "1": {"id":"1","name":"A","owner_id":"owner","state":"idle","inbox":["secret"]},
            "2": {"id":"2","name":"B","owner_id":"other","state":"idle"},
        }
        with patch(
            "core.mcp_bridge_routes.list_agents", return_value=source
        ), patch(
            "core.mcp_bridge_routes.get_visible_agents",
            return_value={"1": source["1"]},
        ) as visible, patch(
            "core.mcp_bridge_routes.has_permission", return_value=True
        ):
            response = self.client.get(
                "/internal/mcp/v1/agents",
                headers={"Authorization": "Bearer bridge-test"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("inbox", response.get_json()["agents"][0])
        visible.assert_called_once_with("owner", source)

    def test_agent_execute_requires_command(self):
        with patch(
            "core.mcp_bridge_routes.has_permission", return_value=True
        ), patch(
            "core.mcp_bridge_routes.list_agents", return_value={
                "1": {"id":"1","name":"A","owner_id":"owner","state":"idle"}
            }
        ), patch(
            "core.mcp_bridge_routes.get_visible_agents",
            return_value={"1": {"id":"1","name":"A","owner_id":"owner","state":"idle"}},
        ), patch(
            "core.mcp_bridge_routes.get_agent",
            return_value=("1", {"id":"1","name":"A","owner_id":"owner","state":"idle"}),
        ):
            response = self.client.post(
                "/internal/mcp/v1/agents/1/execute",
                json={},
                headers={"Authorization": "Bearer bridge-test"},
            )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()