import hashlib
import hmac
import os
import unittest
from unittest.mock import patch

from flask import Flask

from core.mcp_bridge_routes import register_mcp_bridge


class MCPCanonicalBridgeTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        register_mcp_bridge(self.app)
        self.client = self.app.test_client()
        self._token = os.environ.get("SLH_MCP_BRIDGE_TOKEN")
        os.environ["SLH_MCP_BRIDGE_TOKEN"] = "expected"

    def tearDown(self):
        if self._token is None:
            os.environ.pop("SLH_MCP_BRIDGE_TOKEN", None)
        else:
            os.environ["SLH_MCP_BRIDGE_TOKEN"] = self._token

    def _headers(self, principal="owner"):
        signature = hmac.new(
            b"expected",
            principal.encode(),
            hashlib.sha256,
        ).hexdigest()
        return {
            "X-SLH-MCP-Key": "expected",
            "X-SLH-MCP-Principal": principal,
            "X-SLH-MCP-Signature": signature,
        }

    def test_bridge_rejects_bad_signature(self):
        headers = self._headers()
        headers["X-SLH-MCP-Signature"] = "0" * 64
        response = self.client.get(
            "/api/internal/mcp/agents",
            headers=headers,
        )
        self.assertEqual(response.status_code, 403)

    def test_bridge_agent_route_is_authority_backed(self):
        source = {
            "1": {
                "id": "1",
                "name": "alpha",
                "owner_id": "owner",
                "state": "idle",
                "wallet": {"credits": 999},
            }
        }
        with patch("core.mcp_bridge_routes.list_agents", return_value=source),              patch("core.mcp_bridge_routes.get_visible_agents", return_value=source):
            response = self.client.get(
                "/api/internal/mcp/agents",
                headers=self._headers(),
            )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertNotIn("wallet", body["agents"][0])


if __name__ == "__main__":
    unittest.main()
