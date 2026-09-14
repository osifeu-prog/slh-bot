import json
import tempfile
import unittest
from pathlib import Path

import state_manager
from core import agent_submission_service


class AgentSubmissionRewardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "db.json"
        self.db_path.write_text(
            json.dumps({
                "users": {"123": {"wallet": {"credits": 100}}},
                "agent_submissions": [],
                "ledger": [],
                "marketplace": [],
            }),
            encoding="utf-8",
        )
        state_manager.DB_FILE = str(self.db_path)
        state_manager._LOCK_PATH = str(self.db_path) + ".lock"

    def tearDown(self):
        self.tmp.cleanup()

    def _db(self):
        return json.loads(self.db_path.read_text(encoding="utf-8"))

    def test_submission_does_not_pay_creator_before_approval(self):
        result = agent_submission_service.submit_agent("123", "demo-agent")
        self.assertTrue(result["submission_id"].startswith("AS-"))
        db = self._db()
        self.assertEqual(result["reward"], 0)
        self.assertEqual(db["users"]["123"]["wallet"]["credits"], 100)
        self.assertEqual(len(db["agent_submissions"]), 1)
        self.assertEqual(db["agent_submissions"][0]["status"], "pending")
        self.assertEqual(db["ledger"], [])

    def test_duplicate_pending_submission_is_rejected(self):
        agent_submission_service.submit_agent("123", "demo-agent")
        with self.assertRaisesRegex(ValueError, "SUBMISSION_ALREADY_PENDING"):
            agent_submission_service.submit_agent("123", "DEMO-AGENT")

    def test_approval_pays_fixed_reward_once_and_uses_stable_id(self):
        result = agent_submission_service.submit_agent("123", "demo-agent")
        submission_id = result["submission_id"]

        approved = agent_submission_service.approve_agent_submission(submission_id, {"approved_by": "admin"})
        db = self._db()
        self.assertEqual(approved["reward"], 40)
        self.assertEqual(db["users"]["123"]["wallet"]["credits"], 140)
        self.assertEqual(len(db["marketplace"]), 1)
        self.assertEqual(db["marketplace"][0]["submission_id"], submission_id)
        self.assertEqual(len(db["ledger"]), 1)
        self.assertEqual(db["ledger"][0]["amount"], 40)
        self.assertEqual(db["agent_submissions"][0]["status"], "approved")

        with self.assertRaisesRegex(ValueError, "SUBMISSION_NOT_PENDING"):
            agent_submission_service.approve_agent_submission(submission_id)

    def test_stable_ids_survive_other_submission_approval(self):
        first = agent_submission_service.submit_agent("123", "first-agent")
        second = agent_submission_service.submit_agent("123", "second-agent")

        agent_submission_service.approve_agent_submission(first["submission_id"])
        result = agent_submission_service.approve_agent_submission(second["submission_id"])

        db = self._db()
        self.assertEqual(result["agent_name"], "second-agent")
        self.assertEqual(db["users"]["123"]["wallet"]["credits"], 180)
        self.assertEqual(len(db["ledger"]), 2)
        self.assertEqual(len(db["marketplace"]), 2)


if __name__ == "__main__":
    unittest.main()
