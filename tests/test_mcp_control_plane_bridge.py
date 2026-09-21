import unittest
from unittest.mock import MagicMock, patch


class MCPBridgeTests(unittest.TestCase):
    def test_disabled_without_configuration(self):
        import os
        from slh_mcp import control_plane_client
        with patch.dict(os.environ, {
            "SLH_CONTROL_PLANE_URL": "",
            "SLH_MCP_BRIDGE_TOKEN": "",
        }, clear=False):
            self.assertFalse(control_plane_client.enabled())

    def test_authenticated_get(self):
        import os
        from slh_mcp import control_plane_client

        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"agents": []}'
        response.__enter__.return_value.__exit__.return_value = None

        class RequestSpy:
            def __init__(self, url, data=None, headers=None, method=None):
                self.url = url
                self.data = data
                self.headers = headers
                self.method = method

        with patch.dict(os.environ, {
            "SLH_CONTROL_PLANE_URL": "https://control.invalid",
            "SLH_MCP_BRIDGE_TOKEN": "bridge-test",
        }, clear=False), patch(
            "slh_mcp.control_plane_client.urllib.request.urlopen",
            return_value=response,
        ), patch(
            "slh_mcp.control_plane_client.urllib.request.Request",
            side_effect=RequestSpy,
        ) as factory:
            result = control_plane_client.agents()

        self.assertEqual(result, {"agents": []})
        request = factory.call_args[0]
        self.assertEqual(request[0], "https://control.invalid/internal/mcp/v1/agents")
        self.assertEqual(request[2]["Authorization"], "Bearer bridge-test")


if __name__ == "__main__":
    unittest.main()
