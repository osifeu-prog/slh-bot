import asyncio
import os
import unittest

from core.identity import OWNER_TELEGRAM_ID


class MCPProtocolTests(unittest.TestCase):
    def setUp(self):
        os.environ["SLH_MCP_BEARER_TOKEN"] = "test-token"
        os.environ["SLH_MCP_PRINCIPAL_ID"] = str(OWNER_TELEGRAM_ID)

    def test_registered_tool_names_are_stable(self):
        from slh_mcp.server import mcp

        tools = asyncio.run(mcp.list_tools())
        names = {item.name for item in tools}

        expected = {
            "system.health",
            "agents.list",
            "agents.get",
            "agents.runtime_status",
            "agents.execute",
            "missions.list",
            "missions.complete",
            "economy.agent_balance",
            "economy.agent_ledger",
            "economy.propose_transfer",
            "economy.commit_transfer",
            "bots.registry",
            "railway.projects",
            "railway.services",
            "railway.deployments",
            "github.repositories",
            "github.ci_status",
        }
        self.assertTrue(expected.issubset(names))

    def test_health_route_is_public(self):
        from starlette.testclient import TestClient
        from slh_mcp.server import build_mcp_app

        with TestClient(build_mcp_app()) as client:
            response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_mcp_route_requires_bearer(self):
        from starlette.testclient import TestClient
        from slh_mcp.server import build_mcp_app

        with TestClient(build_mcp_app()) as client:
            response = client.post("/mcp", headers={"Host": "localhost"})
        self.assertEqual(response.status_code, 401)

    def test_system_snapshot_is_safe(self):
        from unittest.mock import patch
        from slh_mcp.resources import system_snapshot

        with patch("slh_mcp.resources.agents_resource", return_value=[{}, {}]),              patch("slh_mcp.resources.missions_list", return_value=[{}]):
            result = system_snapshot()
        self.assertEqual(result["agent_count"], 2)
        self.assertEqual(result["mission_count"], 1)
        self.assertNotIn("token", repr(result).lower())


if __name__ == "__main__":
    unittest.main()