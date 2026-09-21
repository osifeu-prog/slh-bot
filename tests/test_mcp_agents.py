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
        with patch("slh_mcp.tools.agents.list_agents", return_value={}):
            with self.assertRaises(KeyError):
                agents_get(self.owner, "missing")

    def test_agent_list_uses_visibility(self):
        from slh_mcp.tools.agents import agents_list
        source = {
            "1": {"id": "1", "name": "alpha", "owner_id": str(OWNER_TELEGRAM_ID), "state": "idle"},
            "2": {"id": "2", "name": "other", "owner_id": "999", "state": "idle"},
        }
        with patch("slh_mcp.tools.agents.list_agents", return_value=source), patch(
            "slh_mcp.tools.agents.get_visible_agents", return_value={"1": source["1"]}
        ) as visible:
            result = agents_list(self.owner)
        visible.assert_called_once_with(self.owner.subject, source)
        self.assertEqual(result, [{"id": "1", "name": "alpha", "state": "idle"}])

    def test_execution_delegates_to_runtime_service(self):
        from slh_mcp.tools.agents import agents_execute
        source = {"1": {"id": "1", "name": "alpha", "owner_id": str(OWNER_TELEGRAM_ID), "state": "idle"}}
        with patch(
            "slh_mcp.tools.agents.list_agents",
            return_value=source,
        ), patch(
            "slh_mcp.tools.agents.get_visible_agents",
            return_value=source,
        ), patch(
            "slh_mcp.tools.agents.get_agent",
            return_value=("1", source["1"]),
        ), patch(
            "slh_mcp.tools.agents.execute_agent",
            return_value={"type": "agent", "data": "pong"},
        ) as execute:
            result = agents_execute(self.owner, "1", "ping")
        execute.assert_called_once_with("1", "ping", source="mcp")
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

    def test_missions_list_reads_canonical_board(self):
        from slh_mcp.tools.missions import missions_list
        board = {
            "missions": [
                {"id": "m1", "desc": "test", "status": "open", "assigned_to": None, "reward": 0},
            ]
        }
        fake_lifecycle = type("FakeLifecycle", (), {
            "load_state": lambda self: (board, {"agents": {"items": []}}),
        })
        with patch("slh_mcp.tools.missions.MissionLifecycleService", fake_lifecycle):
            result = missions_list(self.owner)
        self.assertEqual(result, board["missions"])


if __name__ == "__main__":
    unittest.main()