import unittest


class MCPBootstrapTests(unittest.TestCase):
    def test_builds_asgi_app(self):
        from slh_mcp.server import build_mcp_app

        app = build_mcp_app()
        self.assertTrue(hasattr(app, "routes"))


if __name__ == "__main__":
    unittest.main()
