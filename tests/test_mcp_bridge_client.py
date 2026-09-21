import json
import os
import unittest
from unittest.mock import patch


class MCPBridgeClientTests(unittest.TestCase):
    def setUp(self):
        self.previous = {
            key: os.environ.get(key)
            for key in (
                "SLH_CONTROL_PLANE_URL",
                "SLH_MCP_BRIDGE_TOKEN",
                "SLH_MCP_PRINCIPAL_ID",
            )
        }
        os.environ["SLH_CONTROL_PLANE_URL"] = "https://control.example"
        os.environ["SLH_MCP_BRIDGE_TOKEN"] = "expected"
        os.environ["SLH_MCP_PRINCIPAL_ID"] = "owner"

    def tearDown(self):
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_request_sends_signed_principal(self):
        from slh_mcp import control_plane_client

        captured = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({"authorized": True}).encode("utf-8")

        def fake_urlopen(request, timeout=15):
            captured["headers"] = dict(request.header_items())
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            return Response()

        with patch(
            "slh_mcp.control_plane_client.urllib.request.urlopen",
            side_effect=fake_urlopen,
        ):
            result = control_plane_client.authorize("agents.manage", "owner")

        self.assertTrue(result)
        normalized = {key.lower(): value for key, value in captured["headers"].items()}
        self.assertEqual(normalized["x-slh-mcp-key"], "expected")
        self.assertEqual(normalized["x-slh-mcp-principal"], "owner")
        self.assertEqual(len(normalized["x-slh-mcp-signature"]), 64)
        self.assertEqual(captured["url"], "https://control.example/api/internal/mcp/authorize")


if __name__ == "__main__":
    unittest.main()
