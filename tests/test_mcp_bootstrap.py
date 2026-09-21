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

    def test_resource_registration_uses_unique_uris(self):
        from unittest.mock import MagicMock
        from slh_mcp.resources import register_resources

        uris = []

        def resource(uri, **_kwargs):
            uris.append(uri)
            def decorator(fn):
                return fn
            return decorator

        server = MagicMock()
        server.resource.side_effect = resource
        register_resources(server)

        self.assertEqual(len(uris), len(set(uris)))


if __name__ == "__main__":
    unittest.main()