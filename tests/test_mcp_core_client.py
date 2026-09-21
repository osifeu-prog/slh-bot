import os
import unittest
from unittest.mock import patch


class CoreControlPlaneClientTests(unittest.TestCase):
    def test_client_requires_configured_endpoint_and_key(self):
        from slh_mcp.core_client import CoreControlPlaneClient

        client = CoreControlPlaneClient("http://web.railway.internal:8080", "key", "slh-mcp")
        self.assertEqual(client.base_url, "http://web.railway.internal:8080")
        self.assertEqual(client.principal_id, "slh-mcp")

    def test_request_sets_internal_headers(self):
        from slh_mcp.core_client import CoreControlPlaneClient

        class Response:
            def read(self):
                return b'{"ok":true}'
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        client = CoreControlPlaneClient("http://web.railway.internal:8080", "key", "slh-mcp")
        with patch("slh_mcp.core_client.urllib.request.urlopen", return_value=Response()) as urlopen:
            result = client.get("/api/internal/control-plane/agents")
        req = urlopen.call_args.args[0]
        self.assertEqual(req.get_header("X-slh-internal-key"), "key")
        self.assertEqual(req.get_header("X-slh-principal-id"), "slh-mcp")
        self.assertEqual(result, {"ok": True})


    def test_production_rejects_public_core_url(self):
        from slh_mcp.core_client import configured_client

        with patch.dict(
            os.environ,
            {
                "RAILWAY_SERVICE_NAME": "slh-mcp",
                "SLH_CORE_API_URL": "https://public.example.invalid",
                "SLH_CORE_INTERNAL_KEY": "key",
                "SLH_MCP_SERVICE_PRINCIPAL_ID": "slh-mcp",
            },
            clear=False,
        ):
            with self.assertRaises(RuntimeError):
                configured_client()

    def test_configured_backend_is_detected(self):
        from slh_mcp.core_client import configured_client

        with patch.dict(
            os.environ,
            {
                "SLH_CORE_API_URL": "http://web.railway.internal:8080",
                "SLH_CORE_INTERNAL_KEY": "key",
                "SLH_MCP_SERVICE_PRINCIPAL_ID": "slh-mcp",
            },
            clear=False,
        ):
            client = configured_client()
        self.assertIsNotNone(client)
        self.assertEqual(client.principal_id, "slh-mcp")


if __name__ == "__main__":
    unittest.main()