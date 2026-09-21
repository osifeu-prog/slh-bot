import unittest
from unittest.mock import patch


class AgentStateMCPTests(unittest.TestCase):
    def test_consistency_reports_canonical_source_and_display_numbers(self):
        from slh_mcp.tools.agent_state import agents_consistency
        principal = type(
            "P",
            (),
            {"subject": "owner", "role": "OWNER"},
        )()
        visible = {
            "16": {"id":"16","name":"A","owner_id":"owner","state":"idle","created":"2026-09-01"},
            "28": {"id":"28","name":"B","owner_id":"owner","state":"idle","created":"2026-09-02"},
        }
        audit = {
            "ok": False,
            "db_count": 2,
            "snapshot_count": 14,
            "issues": [{"agent_id":"1","type":"state_drift","db_state":None,"snapshot_state":"idle"}],
        }
        with patch("slh_mcp.tools.agent_state.list_agents", return_value=visible),              patch("slh_mcp.tools.agent_state.get_visible_agents", return_value=visible),              patch("slh_mcp.tools.agent_state.AgentStateStore.audit", return_value=audit):
            result = agents_consistency(principal)
        self.assertEqual(result["canonical_source"], "state/db.json")
        self.assertEqual(result["snapshot_count"], 14)
        self.assertEqual([x["display_number"] for x in result["canonical_visible_agents"]], [1, 2])
        self.assertEqual([x["agent_id"] for x in result["canonical_visible_agents"]], ["16", "28"])
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
