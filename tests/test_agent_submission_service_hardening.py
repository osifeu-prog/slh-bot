import json
import tempfile
import unittest
from pathlib import Path

import state_manager
from core import agent_submission_service


class AgentSubmissionServiceHardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "db.json"
        self.db_path.write_text(json.dumps({
            "users": {"123": {"wallet": {"credits": 100}}},
            "agent_submissions": [],
            "ledger": [],
            "marketplace": [],
        }), encoding="utf-8")
        state_manager.DB_FILE = str(self.db_path)
        state_manager._LOCK_PATH = str(self.db_path) + ".lock"

    def tearDown(self):
        self.tmp.cleanup()

    def test_public_submission_never_credits(self):
        result = agent_submission_service.submit_agent("123", "demo-agent")
        db = json.loads(self.db_path.read_text(encoding="utf-8"))
        self.assertEqual(result["reward"], 0)
        self.assertEqual(db["users"]["123"]["wallet"]["credits"], 100)
        self.assertEqual(db["ledger"], [])

    def test_duplicate_pending_is_case_insensitive(self):
        agent_submission_service.submit_agent("123", "Demo-Agent")
        with self.assertRaisesRegex(ValueError, "SUBMISSION_ALREADY_PENDING"):
            agent_submission_service.submit_agent("123", "demo-agent")

    def test_approval_reward_cannot_be_overridden(self):
        agent_submission_service.submit_agent("123", "demo-agent")
        result = agent_submission_service.approve_agent_submission(0)
        db = json.loads(self.db_path.read_text(encoding="utf-8"))
        self.assertEqual(result["reward"], 40)
        self.assertEqual(db["users"]["123"]["wallet"]["credits"], 140)
        self.assertEqual(db["ledger"][0]["amount"], 40)


if __name__ == "__main__":
    unittest.main()
