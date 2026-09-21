import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class ControlPlaneApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        from core.agent_economy import AgentEconomyService
        self.economy = AgentEconomyService(root=Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_internal_authorization_requires_key_and_permission(self):
        from core.control_plane_api import authorize_internal

        with patch.dict(
            os.environ,
            {"SLH_CORE_INTERNAL_KEY": "expected"},
            clear=False,
        ):
            self.assertTrue(
                authorize_internal(
                    "expected",
                    str(OWNER_TELEGRAM_ID),
                    "agents.view_all",
                )
            )
            self.assertFalse(
                authorize_internal(
                    "wrong",
                    str(OWNER_TELEGRAM_ID),
                    "agents.view_all",
                )
            )

    def test_agent_listing_is_sanitized(self):
        from core.control_plane_api import list_agents_control

        source = {
            "1": {
                "id": "1",
                "name": "alpha",
                "state": "idle",
                "owner_id": str(OWNER_TELEGRAM_ID),
                "inbox": ["secret"],
                "history": ["secret"],
                "permissions": ["*"],
            }
        }
        with patch("core.control_plane_api.list_agents", return_value=source), patch(
            "core.control_plane_api.get_visible_agents", return_value=source
        ):
            rows = list_agents_control(str(OWNER_TELEGRAM_ID))
        self.assertEqual(rows[0]["id"], "1")
        self.assertNotIn("inbox", rows[0])
        self.assertNotIn("history", rows[0])
        self.assertNotIn("permissions", rows[0])
        self.assertNotIn("owner_id", rows[0])

    def test_economy_transfer_uses_canonical_agent_ledger(self):
        from core.control_plane_api import economy_transfer_control
        self.economy.record_revenue(
            amount=50,
            operation_id="rev-1",
            actor=str(OWNER_TELEGRAM_ID),
            reason="test",
            evidence={"event_id": "e1"},
        )
        self.economy.treasury_fund(
            agent_id="1",
            amount=20,
            operation_id="fund-1",
            actor=str(OWNER_TELEGRAM_ID),
            reason="test",
        )
        source = {"1": {"id": "1", "owner_id": str(OWNER_TELEGRAM_ID), "state": "idle"}}
        with patch("core.control_plane_api._ECONOMY_SERVICE", self.economy),              patch("core.control_plane_api.list_agents", return_value=source),              patch("core.control_plane_api.get_visible_agents", return_value=source),              patch("core.control_plane_api.get_agent", return_value=("1", source["1"])):
            result = economy_transfer_control(
                str(OWNER_TELEGRAM_ID),
                "1",
                "2",
                5,
                "transfer-1",
                "test",
            )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(self.economy.balance("1"), 15)
        self.assertEqual(self.economy.balance("2"), 5)

    def test_mission_completion_uses_canonical_lifecycle(self):
        from core.control_plane_api import mission_complete_control

        fake = type(
            "FakeLifecycle",
            (),
            {
                "complete_mission": lambda self, mission_id: {
                    "status": "completed",
                    "mission_id": mission_id,
                }
            },
        )
        with patch("core.control_plane_api.MissionLifecycleService", fake):
            result = mission_complete_control("m1")
        self.assertEqual(result["status"], "completed")


if __name__ == "__main__":
    unittest.main()
