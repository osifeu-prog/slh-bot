import os
import unittest
from unittest.mock import patch


class MCPBridgeModeTests(unittest.TestCase):
    def test_local_agent_mode_when_bridge_is_disabled(self):
        from slh_mcp.tools.agents import agents_list

        class Principal:
            subject = "owner"

        agents = {
            "1": {
                "id": "1",
                "name": "A",
                "owner_id": "owner",
                "state": "idle",
            }
        }
        with patch(
            "slh_mcp.tools.agents.control_plane_client.enabled",
            return_value=False,
        ), patch(
            "slh_mcp.tools.agents.list_agents",
            return_value=agents,
        ), patch(
            "slh_mcp.tools.agents.get_visible_agents",
            return_value=agents,
        ):
            result = agents_list(Principal())

        self.assertEqual(result, agents.values().__class__ if False else [{"id": "1", "name": "A", "state": "idle"}])

    def test_bridge_mode_uses_live_agent_source(self):
        from slh_mcp.tools.agents import agents_list

        class Principal:
            subject = "owner"

        with patch(
            "slh_mcp.tools.agents.control_plane_client.enabled",
            return_value=True,
        ), patch(
            "slh_mcp.tools.agents.control_plane_client.agents",
            return_value={"agents": [{"id": "remote-1", "name": "Remote", "state": "active"}]},
        ):
            result = agents_list(Principal())

        self.assertEqual(
            result,
            [{"id": "remote-1", "name": "Remote", "state": "active"}],
        )


if __name__ == "__main__":
    unittest.main()
