import unittest
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class AgentDisplayNumberingTests(unittest.TestCase):
    def test_owner_agents_are_numbered_from_one_without_changing_ids(self):
        from handlers.agents_handler import format_agent_list

        uid = str(OWNER_TELEGRAM_ID)
        agents = {
            "16": {"id": "16", "name": "רובוטוש", "state": "active", "role": "agent", "owner_id": uid, "created": "2026-09-05T12:00:00"},
            "28": {"id": "28", "name": "ESP_Ledger", "state": "idle", "role": "agent", "owner_id": uid, "created": "2026-09-08T21:31:41"},
        }
        text, mapping = format_agent_list(uid, agents)

        self.assertEqual(mapping, {"1": "16", "2": "28"})
        self.assertIn("1. רובוטוש", text)
        self.assertIn("2. ESP_Ledger", text)
        self.assertNotIn("16 -", text)
        self.assertNotIn("28 -", text)

    def test_numbering_is_deterministic_by_created_then_id(self):
        from handlers.agents_handler import format_agent_list

        uid = str(OWNER_TELEGRAM_ID)
        agents = {
            "28": {"id": "28", "name": "B", "state": "idle", "owner_id": uid, "created": "2026-09-08T00:00:00"},
            "16": {"id": "16", "name": "A", "state": "active", "owner_id": uid, "created": "2026-09-05T00:00:00"},
        }
        _, mapping = format_agent_list(uid, agents)
        self.assertEqual(mapping, {"1": "16", "2": "28"})

    def test_non_owner_only_numbers_visible_agents(self):
        from handlers.agents_handler import format_agent_list

        uid = "123"
        agents = {
            "16": {"id": "16", "name": "system", "state": "active", "role": "agent", "owner_id": "999", "agent_type": "system"},
            "21": {"id": "21", "name": "mine", "state": "idle", "role": "agent", "owner_id": uid},
            "22": {"id": "22", "name": "hidden", "state": "idle", "role": "agent", "owner_id": "888"},
        }
        with patch("handlers.agents_handler.get_visible_agents", return_value={"16": agents["16"], "21": agents["21"]}):
            text, mapping = format_agent_list(uid, agents)
        self.assertEqual(mapping, {"1": "16", "2": "21"})
        self.assertIn("1. system", text)
        self.assertIn("2. mine", text)
        self.assertNotIn("hidden", text)


if __name__ == "__main__":
    unittest.main()
