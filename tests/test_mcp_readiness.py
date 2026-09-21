import os
import unittest


class MCPReadinessTests(unittest.TestCase):
    def test_missing_bridge_configuration_is_not_ready(self):
        from slh_mcp.config import readiness
        old = {name: os.environ.pop(name, None) for name in (
            "SLH_MCP_BEARER_TOKEN",
            "SLH_MCP_PRINCIPAL_ID",
            "SLH_MCP_ALLOWED_HOSTS",
            "SLH_CONTROL_PLANE_URL",
            "SLH_MCP_BRIDGE_TOKEN",
        )}
        try:
            result = readiness()
        finally:
            for name, value in old.items():
                if value is not None:
                    os.environ[name] = value
        self.assertFalse(result["ready"])
        self.assertIn("SLH_CONTROL_PLANE_URL", result["missing"])
        self.assertIn("SLH_MCP_BRIDGE_TOKEN", result["missing"])

    def test_complete_configuration_is_ready(self):
        from slh_mcp.config import readiness
        names = (
            "SLH_MCP_BEARER_TOKEN",
            "SLH_MCP_PRINCIPAL_ID",
            "SLH_MCP_ALLOWED_HOSTS",
            "SLH_CONTROL_PLANE_URL",
            "SLH_MCP_BRIDGE_TOKEN",
        )
        old = {name: os.environ.get(name) for name in names}
        try:
            for name in names:
                os.environ[name] = "configured"
            result = readiness()
        finally:
            for name, value in old.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        self.assertTrue(result["ready"])
        self.assertEqual(result["missing"], [])


if __name__ == "__main__":
    unittest.main()
