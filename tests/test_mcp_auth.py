        from slh_mcp.auth import redact
        value = "Authorization: Bearer secret-value"
        result = redact(value)
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("secret-value", result)

    def test_scope_header_resolves_principal(self):
        from slh_mcp.auth import principal_from_scope

        os.environ["SLH_MCP_BEARER_TOKEN"] = "expected"
        os.environ["SLH_MCP_PRINCIPAL_ID"] = str(OWNER_TELEGRAM_ID)

        scope = {
            "type": "http",
            "headers": [
                (b"host", b"localhost"),
                (b"authorization", b"Bearer expected"),
            ],
        }
        principal = principal_from_scope(scope)
        self.assertIsNotNone(principal)
        self.assertEqual(principal.subject, str(OWNER_TELEGRAM_ID))

    def test_mcp_endpoint_rejects_missing_bearer(self):
        from starlette.testclient import TestClient
        from slh_mcp.server import build_mcp_app

        os.environ["SLH_MCP_BEARER_TOKEN"] = "expected"
        os.environ["SLH_MCP_PRINCIPAL_ID"] = str(OWNER_TELEGRAM_ID)

        with TestClient(build_mcp_app()) as client:
            response = client.post("/mcp", headers={"Host": "localhost"})
            self.assertEqual(response.status_code, 401)

    def test_middleware_allows_valid_bearer_to_downstream(self):
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route
        from starlette.middleware import Middleware
        from starlette.testclient import TestClient
        from slh_mcp.server import MCPAuthMiddleware

        async def downstream(_request):
            return PlainTextResponse("ok")

        os.environ["SLH_MCP_BEARER_TOKEN"] = "expected"
        os.environ["SLH_MCP_PRINCIPAL_ID"] = str(OWNER_TELEGRAM_ID)

        app = Starlette(
            routes=[Route("/", downstream)],
            middleware=[Middleware(MCPAuthMiddleware)],
        )
        with TestClient(app) as client:
            response = client.get(
                "/",
                headers={"Authorization": "Bearer expected"},
            )
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()