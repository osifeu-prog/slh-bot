import os
import unittest
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class MCPProtocolTests(unittest.TestCase):
    def setUp(self):
        self.previous = {
            key: os.environ.get(key)
            for key in (
                "SLH_MCP_BEARER_TOKEN",
                "SLH_MCP_PRINCIPAL_ID",
                "SLH_MCP_ALLOWED_HOSTS",
                "SLH_MCP_ALLOWED_ORIGINS",
            )
        }
        os.environ["SLH_MCP_BEARER_TOKEN"] = "expected"
        os.environ["SLH_MCP_PRINCIPAL_ID"] = str(OWNER_TELEGRAM_ID)
        os.environ["SLH_MCP_ALLOWED_HOSTS"] = "localhost,localhost:*"
        os.environ["SLH_MCP_ALLOWED_ORIGINS"] = "http://localhost"

    def tearDown(self):
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_registered_tool_names_are_stable(self):
        import asyncio
        from slh_mcp.server import mcp

        tools = asyncio.run(mcp.list_tools())
        names = {item.name for item in tools}
        for name in (
            "system.health",
            "system.snapshot",
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
            "bots.federation",
            "railway.projects",
            "railway.services",
            "railway.deployments",
            "github.repositories",
            "github.ci_status",
        ):
            self.assertIn(name, names)

    def test_health_route_is_public(self):
        from starlette.testclient import TestClient
        from slh_mcp.server import build_mcp_app

        with TestClient(build_mcp_app()) as client:
            response = client.get("/health", headers={"Host": "localhost"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_mcp_route_requires_bearer(self):
        from starlette.testclient import TestClient
        from slh_mcp.server import build_mcp_app

        with TestClient(build_mcp_app()) as client:
            response = client.post("/mcp", headers={"Host": "localhost"})
        self.assertEqual(response.status_code, 401)

    def test_mcp_route_exists_once(self):
        from slh_mcp.server import build_mcp_app

        app = build_mcp_app()
        paths = [
            getattr(route, "path", None)
            for route in app.routes
            if getattr(route, "path", None)
        ]
        self.assertEqual(paths.count("/mcp"), 1)
        self.assertNotIn("/mcp/mcp", paths)

    def test_invalid_host_is_rejected(self):
        from starlette.testclient import TestClient
        from slh_mcp.server import build_mcp_app

        with TestClient(build_mcp_app()) as client:
            response = client.post(
                "/mcp",
                headers={
                    "Host": "not-allowed.example",
                    "Authorization": "Bearer expected",
                },
            )
        self.assertEqual(response.status_code, 421)

    def test_authenticated_transport_passes_bearer_gate(self):
        from starlette.testclient import TestClient
        from slh_mcp.server import build_mcp_app

        with patch("slh_mcp.capabilities.authorize", return_value=True):
            with TestClient(build_mcp_app()) as client:
                response = client.post(
                    "/mcp",
                    headers={
                        "Host": "localhost",
                        "Authorization": "Bearer expected",
                    },
                )
        self.assertNotEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
