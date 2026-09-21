import os
import unittest
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class MCPBridgeTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            key: os.environ.get(key)
            for key in ("SLH_MCP_BRIDGE_TOKEN",)
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

    def _headers(self):
        return {
            "X-SLH-MCP-Key": "expected",
            "X-SLH-MCP-Principal": str(OWNER_TELEGRAM_ID),
        }

    def test_bridge_requires_secret(self):
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
        os.environ["SLH_MCP_BRIDGE_TOKEN"] = "expected"
        source = {
            "1": {"id": "1", "name": "alpha", "owner_id": str(OWNER_TELEGRAM_ID), "state": "idle"},
            "2": {"id": "2", "name": "other", "owner_id": "999", "state": "idle"},
        }
        with patch("core.mcp_bridge_routes.list_agents", return_value=source), patch(
            "core.mcp_bridge_routes.get_visible_agents",
            return_value={"1": source["1"]},
        ) as visible:
            with self._client() as client:
                response = client.get(
                    "/api/internal/mcp/agents",
                    headers=self._headers(),
                )
        self.assertEqual(response.status_code, 200)
        visible.assert_called_once_with(str(OWNER_TELEGRAM_ID), source)
        self.assertEqual(response.get_json(), {
            "agents": [{"id": "1", "name": "alpha", "state": "idle"}],
        })

    def test_authorize_route_uses_canonical_authority(self):
        os.environ["SLH_MCP_BRIDGE_TOKEN"] = "expected"
        with patch(
            "core.mcp_bridge_routes.has_permission",
            return_value=True,
        ) as permission:
            with self._client() as client:
                response = client.post(
                    "/api/internal/mcp/authorize",
                    headers=self._headers(),
                    json={"permission": "exec.audit"},
                )
        self.assertEqual(response.status_code, 200)
        permission.assert_called_once_with(str(OWNER_TELEGRAM_ID), "exec.audit")
        self.assertTrue(response.get_json()["authorized"])

    def test_runtime_status_is_safe(self):
        os.environ["SLH_MCP_BRIDGE_TOKEN"] = "expected"
        with patch(
            "core.mcp_bridge_routes.has_permission",
            return_value=True,
        ), patch(
            "core.mcp_bridge_routes.runtime_status",
            return_value={
                "state": "running",
                "running": True,
                "boot_ok": True,
                "queue_size": 0,
                "thread_alive": True,
                "agents": [1, 2],
                "secret": "do-not-return",
            },
        ):
            with self._client() as client:
                response = client.get(
                    "/api/internal/mcp/runtime-status",
                    headers=self._headers(),
                )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["agent_count"], 2)
        self.assertNotIn("secret", body)

    def test_execute_requires_agent_permission_and_delegates(self):
        os.environ["SLH_MCP_BRIDGE_TOKEN"] = "expected"
        source = {"1": {"id": "1", "owner_id": str(OWNER_TELEGRAM_ID)}}
        with patch("core.mcp_bridge_routes.list_agents", return_value=source),              patch("core.mcp_bridge_routes.get_visible_agents", return_value=source),              patch("core.mcp_bridge_routes.get_agent", return_value=("1", source["1"])),              patch("core.mcp_bridge_routes.has_permission", return_value=True),              patch("core.mcp_bridge_routes.execute_agent", return_value={"status":"ok"}) as execute:
            with self._client() as client:
                response = client.post(
                    "/api/internal/mcp/agents/1/execute",
                    headers=self._headers(),
                    json={"command":"ping"},
                )
        self.assertEqual(response.status_code, 200)
        execute.assert_called_once_with("1", "ping", source="mcp")
        self.assertEqual(response.get_json(), {"status":"ok"})

    def test_bridge_never_returns_user_wallet(self):
        os.environ["SLH_MCP_BRIDGE_TOKEN"] = "expected"
        row = {
            "id": "1", "name": "alpha", "owner_id": str(OWNER_TELEGRAM_ID),
            "state": "idle", "wallet": {"credits": 123},
        }
        with patch("core.mcp_bridge_routes.list_agents", return_value={"1": row}),              patch("core.mcp_bridge_routes.get_visible_agents", return_value={"1": row}):
            with self._client() as client:
                response = client.get(
                    "/api/internal/mcp/agents",
                    headers=self._headers(),
                )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("wallet", response.get_json()["agents"][0])


if __name__ == "__main__":
    unittest.main()
