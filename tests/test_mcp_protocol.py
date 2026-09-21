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


if __name__ == "__main__":
    unittest.main()
