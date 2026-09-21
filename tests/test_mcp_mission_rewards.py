import tempfile
import unittest
from pathlib import Path
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
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_reward_amount_comes_from_mission(self):
        from slh_mcp.tools.missions import complete_agent_mission

        mission = {
            "id": "m1",
            "status": "executed",
            "assigned_to": "1",
            "reward": 10,
        }
        service_result = {
            "status": "completed",
            "mission_id": "m1",
            "agent_id": "1",
            "mission_status": "completed",
        }
        with patch(
            "slh_mcp.tools.missions.MissionLifecycleService"
        ) as lifecycle_cls, patch(
            "slh_mcp.tools.missions._SERVICE"
        ) as economy, patch(
            "slh_mcp.tools.missions.list_agents",
            return_value={"1": mission},
        ), patch(
            "slh_mcp.tools.missions.get_visible_agents",
            return_value={"1": mission},
        ), patch(
            "slh_mcp.tools.missions.get_agent",
            return_value=("1", {"id": "1", "owner_id": str(OWNER_TELEGRAM_ID)}),
        ):
            lifecycle_cls.return_value.complete_mission.return_value = service_result
            lifecycle_cls.return_value.load_state.return_value = ({"missions": [mission]}, {})
            lifecycle_cls.return_value.find_mission.return_value = mission
            economy.balance.return_value = 10
            economy.record_reward.return_value = {
                "status": "completed",
                "operation_id": "reward-m1",
                "amount": 10,
            }
            result = complete_agent_mission(
                self.owner,
                "m1",
                "1",
                None,
                "reward-m1",
            )
        lifecycle_cls.return_value.complete_mission.assert_called_once_with("m1")
        economy.record_reward.assert_called_once_with(
            agent_id="1",
            amount=10.0,
            operation_id="reward-m1",
            mission_id="m1",
            actor=str(OWNER_TELEGRAM_ID),
        )
        self.assertEqual(result["status"], "completed")

    def test_reward_failure_returns_pending_without_user_ledger(self):
        from slh_mcp.tools.missions import complete_agent_mission

        mission = {
            "id": "m1",
            "status": "executed",
            "assigned_to": "1",
            "reward": 10,
        }
        with patch(
            "slh_mcp.tools.missions.MissionLifecycleService"
        ) as lifecycle_cls, patch(
            "slh_mcp.tools.missions._SERVICE"
        ) as economy, patch(
            "slh_mcp.tools.missions.list_agents",
            return_value={"1": mission},
        ), patch(
            "slh_mcp.tools.missions.get_visible_agents",
            return_value={"1": mission},
        ), patch(
            "slh_mcp.tools.missions.get_agent",
            return_value=("1", {"id": "1", "owner_id": str(OWNER_TELEGRAM_ID)}),
        ):
            lifecycle_cls.return_value.load_state.return_value = ({"missions": [mission]}, {})
            lifecycle_cls.return_value.find_mission.return_value = mission
            lifecycle_cls.return_value.complete_mission.return_value = {
                "status": "completed",
                "mission_id": "m1",
                "agent_id": "1",
                "mission_status": "completed",
            }
            economy.record_reward.side_effect = ValueError("INSUFFICIENT_AGENT_ECONOMY")
            result = complete_agent_mission(
                self.owner,
                "m1",
                "1",
                None,
                "reward-m1",
            )
        self.assertEqual(result["status"], "reward_pending")
        self.assertEqual(result["reason"], "INSUFFICIENT_AGENT_ECONOMY")


if __name__ == "__main__":
    unittest.main()