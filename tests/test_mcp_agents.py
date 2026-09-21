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

    def test_agent_list_uses_live_bridge(self):
        from slh_mcp.tools.agents import agents_list
        with patch(
            "slh_mcp.tools.agents.control_plane_client.agents",
            return_value={"agents": [{"id":"1","name":"alpha","state":"idle"}]},
        ) as bridge:
            result = agents_list(self.owner)
        bridge.assert_called_once_with(str(OWNER_TELEGRAM_ID))
        self.assertEqual(result, [{"id":"1","name":"alpha","state":"idle"}])

    def test_execution_delegates_to_live_bridge(self):
        from slh_mcp.tools.agents import agents_execute
        with patch(
            "slh_mcp.tools.agents.control_plane_client.agent_execute",
            return_value={"status":"ok"},
        ) as execute:
            result = agents_execute(self.owner, "1", "ping")
        execute.assert_called_once_with(
            "1",
            "ping",
            str(OWNER_TELEGRAM_ID),
        )
        self.assertEqual(result, {"status":"ok"})

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

    def test_missions_list_reads_live_bridge(self):
        from slh_mcp.tools.missions import missions_list
        expected = [{"id":"m1","desc":"test","status":"open","assigned_to":None,"reward":0}]
        with patch(
            "slh_mcp.tools.missions.control_plane_client.missions",
            return_value={"missions": expected},
        ) as bridge:
            result = missions_list(self.owner)
        bridge.assert_called_once_with(str(OWNER_TELEGRAM_ID))
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
