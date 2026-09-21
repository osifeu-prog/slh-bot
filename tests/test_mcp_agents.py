import unittest
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class MCPAgentTests(unittest.TestCase):
    def setUp(self):
        from slh_mcp.auth import Principal
        self.owner = Principal(
            subject=str(OWNER_TELEGRAM_ID),
            role="OWNER",
            permissions=frozenset(),
        )

    def test_missing_agent_is_rejected(self):
        from slh_mcp.tools.agents import agents_get
        with patch(
            "slh_mcp.tools.agents.control_plane_client.agent",
            return_value={},
        ):
            with self.assertRaises(KeyError):
                agents_get(self.owner, "missing")

    def test_agent_list_uses_control_plane_bridge(self):
        from slh_mcp.tools.agents import agents_list
        with patch(
            "slh_mcp.tools.agents.control_plane_client.agents",
            return_value={"agents": [{"id": "1", "name": "alpha", "state": "idle"}]},
        ) as bridge:
            result = agents_list(self.owner)
        bridge.assert_called_once_with(self.owner.subject)
        self.assertEqual(result, [{"id": "1", "name": "alpha", "state": "idle"}])

    def test_execution_delegates_to_control_plane_bridge(self):
        from slh_mcp.tools.agents import agents_execute
        with patch(
            "slh_mcp.tools.agents.control_plane_client.agent_execute",
            return_value={"status": "ok", "type": "agent"},
        ) as execute:
            result = agents_execute(self.owner, "1", "ping")
        execute.assert_called_once_with("1", "ping", self.owner.subject)
        self.assertEqual(result["type"], "agent")

    def test_execution_rejects_empty_and_oversized_commands(self):
        from slh_mcp.tools.agents import agents_execute
        with self.assertRaises(ValueError):
            agents_execute(self.owner, "1", " ")
        with self.assertRaises(ValueError):
            agents_execute(self.owner, "1", "x" * 2001)


class MCPMissionTests(unittest.TestCase):
    def setUp(self):
        from slh_mcp.auth import Principal
        self.owner = Principal(
            subject=str(OWNER_TELEGRAM_ID),
            role="OWNER",
            permissions=frozenset(),
        )

    def test_missions_list_reads_control_plane_board(self):
        from slh_mcp.tools.missions import missions_list
        board = {"missions": [{"id": "m1", "status": "open"}]}
        with patch(
            "slh_mcp.tools.missions.control_plane_client.missions",
            return_value=board,
        ) as bridge:
            result = missions_list(self.owner)
        bridge.assert_called_once_with(self.owner.subject)
        self.assertEqual(result, board["missions"])


if __name__ == "__main__":
    unittest.main()
