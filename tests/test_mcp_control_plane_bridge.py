import unittest
from unittest.mock import patch


class MCPBridgeTests(unittest.TestCase):
    def test_disabled_without_bridge_configuration(self):
        import os
        from slh_mcp import control_plane_client
        with patch.dict(os.environ, {
            "SLH_CONTROL_PLANE_URL": "",
            "SLH_MCP_BRIDGE_TOKEN": "",
        }, clear=False):
            self.assertFalse(control_plane_client.enabled())

    def test_client_sends_authenticated_request(self):
        import os
        from slh_mcp import control_plane_client
        from unittest.mock import MagicMock

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
        ) as request_factory:
            result = control_plane_client.agents("owner")

        self.assertEqual(result, {"agents": []})
        request = request_factory.call_args[0]
        self.assertEqual(request[0], "https://control.invalid/internal/mcp/v1/agents")
        self.assertEqual(request[1], None)
        self.assertEqual(request[2]["Authorization"], "Bearer bridge-test")

    def test_tool_can_switch_to_bridge_mode(self):
        from slh_mcp.tools.agents import agents_list

        with patch("slh_mcp.tools.agents.control_plane_client.enabled", return_value=True), patch(
            "slh_mcp.tools.agents.control_plane_client.agents",
            return_value={"agents": [{"id": "a1", "name": "A"}]},
        ):
            class Principal:
                subject = "owner"
            self.assertEqual(agents_list(Principal()), [{"id": "a1", "name": "A"}])


if __name__ == "__main__":
    unittest.main()
