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

    def _mission(self, status="executed"):
        return {
            "id": "m1",
            "status": status,
            "assigned_to": "1",
            "reward": 10,
        }

    def _patches(self, mission, economy):
        lifecycle_patch = patch("slh_mcp.tools.missions.MissionLifecycleService")
        economy_patch = patch("slh_mcp.tools.missions._SERVICE", economy)
        agents_patch = patch(
            "slh_mcp.tools.missions.list_agents",
            return_value={"1": {"id": "1", "owner_id": str(OWNER_TELEGRAM_ID)}},
        )
        visible_patch = patch(
            "slh_mcp.tools.missions.get_visible_agents",
            return_value={"1": {"id": "1", "owner_id": str(OWNER_TELEGRAM_ID)}},
        )
        agent_patch = patch(
            "slh_mcp.tools.missions.get_agent",
            return_value=("1", {"id": "1", "owner_id": str(OWNER_TELEGRAM_ID)}),
        )
        return lifecycle_patch, economy_patch, agents_patch, visible_patch, agent_patch

    def test_reward_uses_canonical_completed_mission_record(self):
        from slh_mcp.tools.missions import complete_agent_mission
        from unittest.mock import MagicMock

        mission = self._mission()
        economy = MagicMock()
        economy.record_reward.return_value = {
            "status": "completed",
            "operation_id": "mission:m1:agent_reward",
            "amount": 10,
        }

        lifecycle_patch, economy_patch, agents_patch, visible_patch, agent_patch = self._patches(mission, economy)
        with lifecycle_patch as lifecycle_cls, economy_patch, agents_patch, visible_patch, agent_patch:
            lifecycle = lifecycle_cls.return_value
            lifecycle.load_state.return_value = ({"missions": [mission]}, {})
            lifecycle.find_mission.return_value = mission
            lifecycle.complete_mission.return_value = {"status": "completed"}

            result = complete_agent_mission(
                self.owner,
                "m1",
                "1",
                "mission:m1:agent_reward",
            )

        lifecycle.complete_mission.assert_called_once_with("m1")
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
        from unittest.mock import MagicMock

        mission = self._mission(status="assigned")
        economy = MagicMock()

        lifecycle_patch, economy_patch, agents_patch, visible_patch, agent_patch = self._patches(mission, economy)
        with lifecycle_patch as lifecycle_cls, economy_patch, agents_patch, visible_patch, agent_patch:
            lifecycle = lifecycle_cls.return_value
            lifecycle.load_state.return_value = ({"missions": [mission]}, {})
            lifecycle.find_mission.return_value = mission

            result = complete_agent_mission(
                self.owner,
                "m1",
                "1",
                "mission:m1:agent_reward",
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "MISSION_NOT_EXECUTED")
        economy.record_reward.assert_not_called()
        lifecycle.complete_mission.assert_not_called()

    def test_already_completed_mission_cannot_use_new_operation_id(self):
        from slh_mcp.tools.missions import complete_agent_mission

        mission = self._mission(status="completed")
        lifecycle_patch, economy_patch, agents_patch, visible_patch, agent_patch = self._patches(mission, object())
        with lifecycle_patch as lifecycle_cls, economy_patch, agents_patch, visible_patch, agent_patch:
            lifecycle = lifecycle_cls.return_value
            lifecycle.load_state.return_value = ({"missions": [mission]}, {})
            lifecycle.find_mission.return_value = mission

            with self.assertRaises(ValueError):
                complete_agent_mission(
                    self.owner,
                    "m1",
                    "1",
                    "mission:m1:different",
                )

    def test_insufficient_treasury_returns_pending(self):
        from slh_mcp.tools.missions import complete_agent_mission
        from unittest.mock import MagicMock

        mission = self._mission()
        economy = MagicMock()
        economy.record_reward.side_effect = ValueError("INSUFFICIENT_AGENT_ECONOMY")

        lifecycle_patch, economy_patch, agents_patch, visible_patch, agent_patch = self._patches(mission, economy)
        with lifecycle_patch as lifecycle_cls, economy_patch, agents_patch, visible_patch, agent_patch:
            lifecycle = lifecycle_cls.return_value
            lifecycle.load_state.return_value = ({"missions": [mission]}, {})
            lifecycle.find_mission.return_value = mission
            lifecycle.complete_mission.return_value = {"status": "completed"}

            result = complete_agent_mission(
                self.owner,
                "m1",
                "1",
                "mission:m1:agent_reward",
            )

        self.assertEqual(result["status"], "reward_pending")
        self.assertEqual(result["reason"], "INSUFFICIENT_AGENT_ECONOMY")
        economy.record_reward.assert_called_once()


if __name__ == "__main__":
    unittest.main()
