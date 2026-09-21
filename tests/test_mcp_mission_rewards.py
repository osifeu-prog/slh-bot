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

    def _mission(self):
        return {
            "id": "m1",
            "status": "assigned",
            "assigned_to": "1",
            "reward": 10,
        }

    def test_reward_amount_comes_from_mission(self):
        from slh_mcp.tools.missions import complete_agent_mission

        mission = self._mission()
        verified_result = {
            "execution_status": "success",
            "verified": True,
            "evidence": {"proof": "ok"},
            "mission_id": "m1",
            "action_type": "test",
            "idempotency_key": "mission-op-1",
        }
        lifecycle_result = {
            "status": "executed",
            "mission_id": "m1",
            "agent_id": "1",
        }

        with patch(
            "slh_mcp.tools.missions.MissionLifecycleService"
        ) as lifecycle_cls, patch(
            "slh_mcp.tools.missions._SERVICE"
        ) as economy, patch(
            "slh_mcp.tools.missions.list_agents",
            return_value={"1": {"id": "1", "owner_id": str(OWNER_TELEGRAM_ID)}},
        ), patch(
            "slh_mcp.tools.missions.get_visible_agents",
            return_value={"1": {"id": "1", "owner_id": str(OWNER_TELEGRAM_ID)}},
        ), patch(
            "slh_mcp.tools.missions.get_agent",
            return_value=("1", {"id": "1", "owner_id": str(OWNER_TELEGRAM_ID)}),
        ):
            lifecycle = lifecycle_cls.return_value
            lifecycle.load_state.return_value = ({"missions": [mission]}, {})
            lifecycle.find_mission.return_value = mission
            lifecycle.execute_mission.return_value = lifecycle_result
            economy.record_reward.return_value = {
                "status": "completed",
                "operation_id": "reward-m1",
                "amount": 10,
            }

            result = complete_agent_mission(
                self.owner,
                "m1",
                "1",
                verified_result,
                "reward-m1",
            )

        lifecycle.execute_mission.assert_called_once_with(
            "m1", execution_result=verified_result
        )
        economy.record_reward.assert_called_once_with(
            agent_id="1",
            amount=10.0,
            operation_id="reward-m1",
            mission_id="m1",
            actor=str(OWNER_TELEGRAM_ID),
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["reward"], 10.0)

    def test_reward_failure_returns_pending_without_user_ledger(self):
        from slh_mcp.tools.missions import complete_agent_mission

        mission = self._mission()
        verified_result = {
            "execution_status": "success",
            "verified": True,
            "evidence": {"proof": "ok"},
            "mission_id": "m1",
            "action_type": "test",
            "idempotency_key": "mission-op-1",
        }

        with patch(
            "slh_mcp.tools.missions.MissionLifecycleService"
        ) as lifecycle_cls, patch(
            "slh_mcp.tools.missions._SERVICE"
        ) as economy, patch(
            "slh_mcp.tools.missions.list_agents",
            return_value={"1": {"id": "1", "owner_id": str(OWNER_TELEGRAM_ID)}},
        ), patch(
            "slh_mcp.tools.missions.get_visible_agents",
            return_value={"1": {"id": "1", "owner_id": str(OWNER_TELEGRAM_ID)}},
        ), patch(
            "slh_mcp.tools.missions.get_agent",
            return_value=("1", {"id": "1", "owner_id": str(OWNER_TELEGRAM_ID)}),
        ):
            lifecycle = lifecycle_cls.return_value
            lifecycle.load_state.return_value = ({"missions": [mission]}, {})
            lifecycle.find_mission.return_value = mission
            lifecycle.execute_mission.return_value = {
                "status": "executed",
                "mission_id": "m1",
                "agent_id": "1",
            }
            economy.record_reward.side_effect = ValueError(
                "INSUFFICIENT_AGENT_ECONOMY"
            )

            result = complete_agent_mission(
                self.owner,
                "m1",
                "1",
                verified_result,
                "reward-m1",
            )

        self.assertEqual(result["status"], "reward_pending")
        self.assertEqual(result["reason"], "INSUFFICIENT_AGENT_ECONOMY")
        economy.record_reward.assert_called_once()


if __name__ == "__main__":
    unittest.main()
