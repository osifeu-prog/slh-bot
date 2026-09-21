import os
import unittest

from core.identity import OWNER_TELEGRAM_ID


class MCPAuthTests(unittest.TestCase):
    def setUp(self):
        self._env = {
            "SLH_MCP_BEARER_TOKEN": os.environ.get("SLH_MCP_BEARER_TOKEN"),
            "SLH_MCP_SERVICE_PRINCIPAL_ID": os.environ.get("SLH_MCP_SERVICE_PRINCIPAL_ID"),
        }

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_missing_token_has_no_principal(self):
        from slh_mcp.auth import Principal
        self.assertIsNone(
            Principal.from_headers({}, "expected", "owner", None, ())
        )

    def test_wrong_token_has_no_principal(self):
        from slh_mcp.auth import Principal
        self.assertIsNone(
            Principal.from_headers(
                {"authorization": "Bearer wrong"},
                "expected",
                "owner",
                None,
                (),
            )
        )

    def test_valid_token_resolves_principal(self):
        from slh_mcp.auth import Principal
        principal = Principal.from_headers(
            {"Authorization": "Bearer expected"},
            "expected",
            str(OWNER_TELEGRAM_ID),
            None,
            (),
        )
        self.assertIsNotNone(principal)
        self.assertEqual(principal.subject, str(OWNER_TELEGRAM_ID))

    def test_owner_authorization_uses_canonical_authority(self):
        from slh_mcp.auth import Principal, authorize
        principal = Principal(
            subject=str(OWNER_TELEGRAM_ID),
            role="OWNER",
            permissions=frozenset(),
        )
        self.assertTrue(authorize(principal, "exec.audit"))

    def test_unknown_principal_is_denied(self):
        from slh_mcp.auth import Principal, authorize
        principal = Principal(
            subject="1",
            role="UNKNOWN",
            permissions=frozenset(),
        )
        self.assertFalse(authorize(principal, "exec.audit"))

    def test_redaction_masks_bearer(self):
        from slh_mcp.auth import redact
        value = "Authorization: Bearer secret-value"
        result = redact(value)
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("secret-value", result)

    def test_scope_header_resolves_principal(self):
        from slh_mcp.auth import principal_from_scope

        os.environ["SLH_MCP_BEARER_TOKEN"] = "expected"
        os.environ["SLH_MCP_SERVICE_PRINCIPAL_ID"] = "slh-mcp"

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