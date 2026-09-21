import unittest

from core.agent_display import (
    format_numbered_agents,
    resolve_display_agent,
)


class AgentDisplayNumberingTests(unittest.TestCase):
    def setUp(self):
        self.agents = {
            "16": {"id": "16", "name": "Robotush", "owner_id": "100", "state": "active", "role": "agent"},
            "28": {"id": "28", "name": "ESP_Ledger", "owner_id": "100", "state": "idle", "role": "agent"},
            "31": {"id": "31", "name": "Other", "owner_id": "200", "state": "idle", "role": "agent"},
        }

    def test_personal_agents_are_numbered_from_one(self):
        rows = format_numbered_agents("100", self.agents)
        self.assertEqual([row["display_id"] for row in rows], [1, 2])
        self.assertEqual([row["id"] for row in rows], ["16", "28"])

    def test_internal_ids_are_preserved(self):
        rows = format_numbered_agents("100", self.agents)
        self.assertEqual(rows[0]["id"], "16")
        self.assertEqual(rows[1]["id"], "28")

    def test_display_id_resolves_to_canonical_id(self):
        self.assertEqual(resolve_display_agent("100", self.agents, "1"), "16")
        self.assertEqual(resolve_display_agent("100", self.agents, "2"), "28")

    def test_canonical_id_still_resolves(self):
        self.assertEqual(resolve_display_agent("100", self.agents, "28"), "28")
        self.assertEqual(resolve_display_agent("100", self.agents, "ESP_Ledger"), "28")

    def test_other_users_agents_are_not_numbered_as_personal(self):
        rows = format_numbered_agents("100", self.agents)
        self.assertNotIn("31", [row["id"] for row in rows])


if __name__ == "__main__":
    unittest.main()
