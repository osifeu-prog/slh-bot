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


    def test_exchange_gate_status_returns_only_canonical_gate_value(self):
        with patch(
            "core.mcp_bridge_routes.has_permission", return_value=True
        ), patch(
            "core.railway_control.exchange_gate_variable_status",
            return_value={
                "variable": "SLH_EXCHANGE_PUBLIC_OPEN",
                "configured": "0",
                "configured_open": False,
                "source": "railway_service_production",
            },
        ):
            response = self.client.get(
                "/internal/mcp/v1/exchange-gate",
                headers={"Authorization": "Bearer bridge-test"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"status": "PASS", "configured": "0", "configured_open": False},
        )

    def test_exchange_gate_close_is_fixed_and_close_only(self):
        result = {
            "status": "DEPLOY_TRIGGERED",
            "configured": "0",
            "commit": "a" * 40,
            "deployment_id": "dep-safe-123",
            "service": "slh-cloud-bot",
            "environment": "production",
        }
        with patch(
            "core.mcp_bridge_routes.has_permission", return_value=True
        ), patch(
            "core.railway_control.close_exchange_gate", return_value=result
        ) as close:
            response = self.client.post(
                "/internal/mcp/v1/exchange-gate/close",
                json={"projectId": "attacker", "value": "1"},
                headers={"Authorization": "Bearer bridge-test"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "status": "DEPLOY_TRIGGERED",
                "configured": "0",
                "commit": "a" * 40,
                "deployment_id": "dep-safe-123",
            },
        )
        close.assert_called_once_with()
        self.assertEqual(
            self.client.post(
                "/internal/mcp/v1/exchange-gate/open",
                headers={"Authorization": "Bearer bridge-test"},
            ).status_code,
            404,
        )

    def test_exchange_gate_close_requires_privileged_bridge_identity(self):
        with patch(
            "core.mcp_bridge_routes.has_permission", return_value=False
        ), patch("core.railway_control.close_exchange_gate") as close:
            response = self.client.post(
                "/internal/mcp/v1/exchange-gate/close",
                headers={"Authorization": "Bearer bridge-test"},
            )
        self.assertEqual(response.status_code, 403)
        close.assert_not_called()


if __name__ == "__main__":
    unittest.main()