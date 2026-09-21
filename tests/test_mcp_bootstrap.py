import unittest


class MCPBootstrapTests(unittest.TestCase):
    def test_builds_asgi_app(self):
        from slh_mcp.server import build_mcp_app

        app = build_mcp_app()
        self.assertTrue(hasattr(app, "routes"))

    def test_sdk_app_exposes_mcp_endpoint(self):
        from slh_mcp.server import mcp

        inner = mcp.streamable_http_app()
        paths = {getattr(route, "path", None) for route in inner.routes}
        self.assertIn("/mcp", paths)


if __name__ == "__main__":
    unittest.main()