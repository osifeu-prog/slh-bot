import unittest
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class MissionRewardTests(unittest.TestCase):
    def setUp(self):
        from slh_mcp.auth import Principal
        self.owner = Principal(
            subject=str(OWNER_TELEGRAM_ID),
            role="OWNER",
            permissions=frozenset(),
        )

    def test_reward_amount_comes_from_live_mission(self):
        from slh_mcp.tools.missions import complete_agent_mission
        mission = {
            "id": "m1",
            "status": "executed",
            "assigned_to": "1",
            "reward": 10,
        }
        with patch(
            "slh_mcp.tools.missions.control_plane_client.mission",
            return_value={"mission": mission},
        ), patch(
            "slh_mcp.tools.missions.control_plane_client.mission_complete",
            return_value={"status": "completed"},
        ), patch(
            "slh_mcp.tools.missions._SERVICE",
        ) as economy:
            economy.record_reward.return_value = {
                "status": "completed",
                "operation_id": "mission:m1:agent_reward",
                "amount": 10,
            }
            result = complete_agent_mission(
                self.owner,
                "m1",
                "1",
                {"result": "ok"},
                "mission:m1:agent_reward",
            )
        economy.record_reward.assert_called_once_with(
            agent_id="1",
            amount=10.0,
            operation_id="mission:m1:agent_reward",
            mission_id="m1",
            actor=str(OWNER_TELEGRAM_ID),
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["reward"], 10.0)

    def test_non_executed_mission_is_blocked(self):
        from slh_mcp.tools.missions import complete_agent_mission
        mission = {
            "id": "m1",
            "status": "assigned",
            "assigned_to": "1",
            "reward": 10,
        }
        with patch(
            "slh_mcp.tools.missions.control_plane_client.mission",
            return_value={"mission": mission},
        ), patch(
            "slh_mcp.tools.missions._SERVICE",
        ) as economy:
            result = complete_agent_mission(
                self.owner,
                "m1",
                "1",
                None,
                "mission:m1:agent_reward",
            )
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "MISSION_NOT_EXECUTED")
        economy.record_reward.assert_not_called()

    def test_completed_mission_is_idempotent_at_operation_boundary(self):
        from slh_mcp.tools.missions import complete_agent_mission
        mission = {
            "id": "m1",
            "status": "completed",
            "assigned_to": "1",
            "reward": 10,
        }
        with patch(
            "slh_mcp.tools.missions.control_plane_client.mission",
            return_value={"mission": mission},
        ), patch(
            "slh_mcp.tools.missions._SERVICE",
        ) as economy:
            result = complete_agent_mission(
                self.owner,
                "m1",
                "1",
                None,
                "mission:m1:agent_reward",
            )
        self.assertEqual(result["status"], "already_completed")
        economy.record_reward.assert_not_called()

    def test_insufficient_treasury_returns_pending(self):
        from slh_mcp.tools.missions import complete_agent_mission
        mission = {
            "id": "m1",
            "status": "executed",
            "assigned_to": "1",
            "reward": 10,
        }
        with patch(
            "slh_mcp.tools.missions.control_plane_client.mission",
            return_value={"mission": mission},
        ), patch(
            "slh_mcp.tools.missions.control_plane_client.mission_complete",
            return_value={"status": "completed"},
        ), patch(
            "slh_mcp.tools.missions._SERVICE",
        ) as economy:
            economy.record_reward.side_effect = ValueError(
                "INSUFFICIENT_AGENT_ECONOMY"
            )
            result = complete_agent_mission(
                self.owner,
                "m1",
                "1",
                None,
                "mission:m1:agent_reward",
            )
        self.assertEqual(result["status"], "reward_pending")
        self.assertEqual(result["reason"], "INSUFFICIENT_AGENT_ECONOMY")


if __name__ == "__main__":
    unittest.main()
