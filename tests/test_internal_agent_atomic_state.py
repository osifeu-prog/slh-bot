import ast
import copy
import unittest
from unittest.mock import patch

import internal_agent


def _db():
    return {
        "users": {"owner": {}},
        "agents": {
            "alpha": {
                "inbox": [{"command": "whoami"}, {"command": "status"}],
                "outbox": [],
            },
            "tutor": {"inbox": [{"command": "hello"}], "outbox": []},
        },
        "students": {
            "student-1": {"points": 2, "completed_tasks": []},
        },
        "courses": {
            "bitcoin_mastery": {
                "tasks": {
                    "task-1": {"reward": 5, "validation": ""},
                },
            },
        },
    }


class InternalAgentAtomicStateTests(unittest.TestCase):
    def setUp(self):
        self.db = _db()

    def _atomic_update(self, mutate):
        return mutate(self.db)

    def test_agent_claim_moves_messages_to_processing_without_losing_tutor_inbox(self):
        with patch.object(internal_agent.state_manager, "atomic_update", side_effect=self._atomic_update):
            claimed = internal_agent._claim_inbox(exclude_agents={"tutor"})

        self.assertEqual(len(claimed), 2)
        self.assertEqual(self.db["agents"]["alpha"]["inbox"], [])
        self.assertEqual(len(self.db["agents"]["alpha"]["processing"]), 2)
        self.assertEqual(self.db["agents"]["tutor"]["inbox"], [{"command": "hello"}])
        self.assertEqual(self.db["agents"]["tutor"].get("processing", []), [])

    def test_finalize_is_atomic_and_caps_outbox(self):
        with patch.object(internal_agent.state_manager, "atomic_update", side_effect=self._atomic_update):
            claimed = internal_agent._claim_inbox(exclude_agents={"tutor"})
            name, claim_id, _message = claimed[0]
            for index in range(25):
                internal_agent._finalize_message(name, claim_id if index == 0 else "missing", f"output-{index}")

        self.assertEqual(len(self.db["agents"]["alpha"]["processing"]), 1)
        self.assertEqual(self.db["agents"]["alpha"]["outbox"], ["output-0"])

    def test_finalize_does_not_append_output_for_missing_or_expired_claim(self):
        with patch.object(internal_agent.state_manager, "atomic_update", side_effect=self._atomic_update):
            self.assertFalse(internal_agent._finalize_message("alpha", "not-a-claim", "duplicate"))

        self.assertEqual(self.db["agents"]["alpha"]["outbox"], [])

    def test_complete_task_awards_points_once(self):
        with (
            patch.object(internal_agent.state_manager, "load_db", side_effect=lambda: copy.deepcopy(self.db)),
            patch.object(internal_agent.state_manager, "atomic_update", side_effect=self._atomic_update),
        ):
            first = internal_agent.complete_task("student-1", "task-1")
            second = internal_agent.complete_task("student-1", "task-1")

        self.assertEqual(first, "✅ Task task-1 completed! +5 points")
        self.assertIn("already completed", second)
        self.assertEqual(self.db["students"]["student-1"]["points"], 7)
        self.assertEqual(self.db["students"]["student-1"]["completed_tasks"], ["task-1"])

    def test_task_completion_does_not_award_points_if_atomic_update_retries(self):
        with (
            patch.object(internal_agent.state_manager, "load_db", side_effect=lambda: copy.deepcopy(self.db)),
            patch.object(internal_agent.state_manager, "atomic_update", side_effect=self._atomic_update),
        ):
            internal_agent.complete_task("student-1", "task-1")
            internal_agent.complete_task("student-1", "task-1")
            internal_agent.complete_task("student-1", "task-1")

        self.assertEqual(self.db["students"]["student-1"]["points"], 7)

    def test_module_has_no_direct_root_db_json_reads_or_writes(self):
        source = open(internal_agent.__file__, encoding="utf-8").read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "open" and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and arg.value == "db.json":
                    self.fail("internal_agent.py must not access root db.json directly")

    def test_tutor_and_general_workers_have_separate_inboxes(self):
        with patch.object(internal_agent.state_manager, "atomic_update", side_effect=self._atomic_update):
            general = internal_agent._claim_inbox(exclude_agents={"tutor"})
            tutor = internal_agent._claim_inbox(agent_filter={"tutor"})

        self.assertEqual([item[0] for item in general], ["alpha", "alpha"])
        self.assertEqual([item[0] for item in tutor], ["tutor"])
        self.assertEqual(self.db["agents"]["alpha"]["inbox"], [])
        self.assertEqual(self.db["agents"]["tutor"]["inbox"], [])


if __name__ == "__main__":
    unittest.main()
