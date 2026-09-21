import unittest


class MCPBootstrapTests(unittest.TestCase):
    def test_builds_asgi_app(self):
        from slh_mcp.server import build_mcp_app

        app = build_mcp_app()
        self.assertTrue(hasattr(app, "routes"))

    def test_mcp_host_mount_preserves_inner_mcp_endpoint(self):
        from slh_mcp.server import build_mcp_app

        app = build_mcp_app()
        mounts = [route for route in app.routes if getattr(route, "path", None) == "/"]
        self.assertTrue(mounts)
        inner = mounts[0].app
        inner_paths = {getattr(route, "path", None) for route in inner.routes}
        self.assertIn("/mcp", inner_paths)


if __name__ == "__main__":
    unittest.main()