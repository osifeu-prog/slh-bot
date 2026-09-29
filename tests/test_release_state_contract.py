import unittest
from unittest.mock import patch

from core.control_center import get_release_state


class TestReleaseStateContract(unittest.TestCase):
    def test_release_state_is_read_only_and_structured(self):
        with patch("core.control_center._load_json", return_value={}),              patch("core.control_center.state_manager.get_agents", return_value={}),              patch("core.control_center.run_system_checks", create=True, return_value={"status": "PASS"}):
            state = get_release_state()

        self.assertEqual(state["scope"], "read_only")
        self.assertIn(state["overall"], {"GREEN", "DEGRADED", "BLOCKED"})
        self.assertIn("readiness", state)
        self.assertIn("current_state", state)
        self.assertEqual(state["current_state"]["bnb_settlement"], "CLOSED")
        self.assertEqual(state["current_state"]["ton_settlement"], "CLOSED")
        self.assertIsInstance(state["auto_actions"], list)
        self.assertIsInstance(state["owner_actions"], list)


if __name__ == "__main__":
    unittest.main()
