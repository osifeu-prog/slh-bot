import unittest
from unittest.mock import patch

from core.control_center import get_release_state


class TestReleaseStateContract(unittest.TestCase):
    def test_release_state_is_read_only_and_structured(self):
        with patch("core.system_check.run_system_checks", return_value={"status": "PASS"}), \
             patch("core.alpha_control_plane.evaluate", return_value={"status": "READY", "system_status": "READY"}), \
             patch("core.alpha_control_plane.alpha_state", return_value={"status": "CLOSED"}), \
             patch("core.bnb_gate.bnb_readiness", return_value={"effective_open": False}), \
             patch("core.ton_deposit_service.deposits_are_open", return_value=False), \
             patch("core.control_center._load_registry", return_value={"schema_version": "test", "railway_projects": []}):
            state = get_release_state()

        self.assertEqual(state["scope"], "read_only")
        self.assertEqual(state["overall"], "GREEN")
        self.assertEqual(state["readiness"]["runtime"], "READY")
        self.assertEqual(state["readiness"]["alpha"], "READY")
        self.assertEqual(state["current_state"]["alpha"], "CLOSED")
        self.assertEqual(state["current_state"]["bnb_settlement"], "CLOSED")
        self.assertEqual(state["current_state"]["ton_settlement"], "CLOSED")
        self.assertIsInstance(state["auto_actions"], list)
        self.assertIsInstance(state["owner_actions"], list)


if __name__ == "__main__":
    unittest.main()
