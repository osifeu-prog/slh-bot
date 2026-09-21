    def test_redaction_masks_bearer(self):
        from slh_mcp.auth import redact
        value = "Authorization: Bearer secret-value"
        result = redact(value)
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("secret-value", result)

    def test_mcp_endpoint_rejects_missing_bearer(self):
        import os
        from starlette.testclient import TestClient
        from slh_mcp.server import build_mcp_app

        os.environ["SLH_MCP_BEARER_TOKEN"] = "expected"
        os.environ["SLH_MCP_PRINCIPAL_ID"] = str(OWNER_TELEGRAM_ID)

        with TestClient(build_mcp_app()) as client:
            response = client.post("/mcp", headers={"Host": "localhost"})
            self.assertEqual(response.status_code, 401)

    def test_mcp_endpoint_accepts_valid_bearer_past_auth(self):
        import os
        from starlette.testclient import TestClient
        from slh_mcp.server import build_mcp_app

        os.environ["SLH_MCP_BEARER_TOKEN"] = "expected"
        os.environ["SLH_MCP_PRINCIPAL_ID"] = str(OWNER_TELEGRAM_ID)

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