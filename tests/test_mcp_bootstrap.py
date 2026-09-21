import unittest


class MCPBootstrapTests(unittest.TestCase):
    def test_builds_asgi_app(self):
        from slh_mcp.server import build_mcp_app

        app = build_mcp_app()
        self.assertTrue(hasattr(app, "routes"))

    def test_mcp_route_is_mounted_at_expected_path(self):
        from slh_mcp.server import build_mcp_app

        app = build_mcp_app()
        paths = {getattr(route, "path", None) for route in app.routes}
        self.assertIn("/mcp", paths)


if __name__ == "__main__":
    unittest.main()
