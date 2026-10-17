import ast
import copy
import importlib
import os
import unittest
from unittest.mock import MagicMock, patch

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

    def test_legacy_text_message_is_treated_as_a_question_not_a_command(self):
        self.db["agents"]["alpha"]["inbox"] = ["restart"]

        with patch.object(internal_agent.state_manager, "atomic_update", side_effect=self._atomic_update):
            claimed = internal_agent._claim_inbox(exclude_agents={"tutor"})

        self.assertEqual(len(claimed), 1)
        self.assertEqual(
            claimed[0][2],
            {"command": "ask", "prompt": "restart", "uid": ""},
        )

    def test_ask_uses_the_configured_provider_fallback_chain(self):
        with patch(
            "handlers.llm_handler.query_llm_with_context",
            return_value="answer from canonical AI fallback",
        ) as query:
            result = internal_agent.run_command(
                "ask", {"prompt": "Explain this safely", "uid": "owner"}
            )

        self.assertEqual(result, "answer from canonical AI fallback")
        query.assert_called_once_with("Explain this safely", uid="owner")

    def test_legacy_restart_command_is_disabled_even_for_owner(self):
        with patch("core.authority.is_owner", return_value=True), patch.object(
            internal_agent.os, "system"
        ) as system_call:
            result = internal_agent.run_command("restart", {"uid": "owner"})

        self.assertEqual(result, "Unknown: restart")
        system_call.assert_not_called()

    def test_sensitive_agent_commands_require_owner_identity(self):
        with patch("core.authority.is_owner", return_value=False), patch.object(
            internal_agent.os, "system"
        ) as system_call:
            result = internal_agent.run_command("restart", {"uid": "123"})

        self.assertEqual(result, "OWNER_ONLY")
        system_call.assert_not_called()

    def test_agent_claim_moves_one_message_to_processing_without_losing_other_inboxes(self):
        with patch.object(internal_agent.state_manager, "atomic_update", side_effect=self._atomic_update):
            claimed = internal_agent._claim_inbox(exclude_agents={"tutor"})

        self.assertEqual(len(claimed), 1)
        self.assertEqual(self.db["agents"]["alpha"]["inbox"], [{"command": "status"}])
        self.assertEqual(len(self.db["agents"]["alpha"]["processing"]), 1)
        self.assertEqual(self.db["agents"]["tutor"]["inbox"], [{"command": "hello"}])
        self.assertEqual(self.db["agents"]["tutor"].get("processing", []), [])

    def test_finalize_caps_outbox_and_removes_only_its_claim(self):
        self.db["agents"]["alpha"]["outbox"] = [f"old-{index}" for index in range(25)]
        with patch.object(internal_agent.state_manager, "atomic_update", side_effect=self._atomic_update):
            claimed = internal_agent._claim_inbox(exclude_agents={"tutor"})
            name, claim_id, _message = claimed[0]
            finalized = internal_agent._finalize_message(name, claim_id, "new-output")

        self.assertTrue(finalized)
        self.assertEqual(len(self.db["agents"]["alpha"]["outbox"]), 20)
        self.assertEqual(self.db["agents"]["alpha"]["outbox"][-1], "new-output")
        self.assertEqual(self.db["agents"]["alpha"]["processing"], [])
        self.assertEqual(self.db["agents"]["alpha"]["inbox"], [{"command": "status"}])

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
        with open(internal_agent.__file__, encoding="utf-8") as source_file:
            source = source_file.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "open" and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and arg.value == "db.json":
                    self.fail("internal_agent.py must not access root db.json directly")

    def test_actual_agent_worker_claims_ask_and_finalizes_outbox_result(self):
        payload = {
            "command": "ask",
            "prompt": "Summarize readiness without executing actions",
            "uid": "owner",
            "request_id": "telegram:owner:555:900",
        }
        self.db["agents"]["alpha"]["inbox"] = [payload]
        self.db["agents"]["alpha"]["processing"] = []

        class StopWorker(BaseException):
            """Stop the background loop after its first complete iteration."""

        with (
            patch.object(
                internal_agent.state_manager,
                "atomic_update",
                side_effect=self._atomic_update,
            ),
            patch(
                "handlers.llm_handler.query_llm_with_context",
                return_value="answer from configured SLH fallback",
            ) as query,
            patch.object(internal_agent.time, "sleep", side_effect=StopWorker),
        ):
            with self.assertRaises(StopWorker):
                internal_agent.agent_worker()

        query.assert_called_once_with(
            "Summarize readiness without executing actions",
            uid="owner",
        )
        agent = self.db["agents"]["alpha"]
        self.assertEqual(agent["inbox"], [])
        self.assertEqual(agent["processing"], [])
        self.assertEqual(len(agent["outbox"]), 1)
        self.assertIn("answer from configured SLH fallback", agent["outbox"][0])
        self.assertIn("ask", agent["outbox"][0])

    def test_tutor_and_general_workers_claim_separate_inboxes(self):
        with patch.object(internal_agent.state_manager, "atomic_update", side_effect=self._atomic_update):
            general = internal_agent._claim_inbox(exclude_agents={"tutor"})
            tutor = internal_agent._claim_inbox(agent_filter={"tutor"})

        self.assertEqual([item[0] for item in general], ["alpha"])
        self.assertEqual([item[0] for item in tutor], ["tutor"])
        self.assertEqual(self.db["agents"]["alpha"]["inbox"], [{"command": "status"}])
        self.assertEqual(self.db["agents"]["tutor"]["inbox"], [])

    def test_expired_claim_is_requeued(self):
        self.db["agents"]["alpha"]["processing"] = [{
            "claim_id": "expired",
            "message": {"command": "whoami"},
            "claimed_at": 0,
        }]
        self.db["agents"]["alpha"]["inbox"] = []
        with patch.object(internal_agent.state_manager, "atomic_update", side_effect=self._atomic_update):
            claimed = internal_agent._claim_inbox(exclude_agents={"tutor"})

        self.assertEqual(len(claimed), 1)
        self.assertEqual(claimed[0][2], {"command": "whoami"})
        self.assertNotEqual(claimed[0][1], "expired")
        self.assertEqual(self.db["agents"]["alpha"]["processing"][0]["claim_id"], claimed[0][1])


    def test_worker_autostart_is_gated_by_run_bot(self):
        with (
            patch.dict(os.environ, {"RUN_BOT": "0"}),
            patch.object(internal_agent, "start_agent_thread") as start,
        ):
            internal_agent._maybe_start_workers()
            start.assert_not_called()

        with (
            patch.dict(os.environ, {"RUN_BOT": "1"}),
            patch.object(internal_agent, "start_agent_thread") as start,
        ):
            internal_agent._maybe_start_workers()
            start.assert_called_once_with()


    def test_module_import_starts_both_workers_only_when_run_bot_enabled(self):
        # Reload the module with Thread mocked to test the actual import-time path
        # without spawning worker loops inside the test runner.
        try:
            threads = [MagicMock(), MagicMock()]
            with (
                patch.dict(os.environ, {"RUN_BOT": "1"}),
                patch("threading.Thread", side_effect=threads) as thread_class,
            ):
                importlib.reload(internal_agent)
                self.assertEqual(thread_class.call_count, 2)
                names = [call.kwargs.get("name") for call in thread_class.call_args_list]
                self.assertCountEqual(names, ["agent_worker", "tutor_worker"])
                self.assertEqual([thread.start.call_count for thread in threads], [1, 1])
        finally:
            # Restore the module to a test-safe state; no workers are started here.
            with patch.dict(os.environ, {"RUN_BOT": "0"}):
                importlib.reload(internal_agent)


if __name__ == "__main__":
    unittest.main()
