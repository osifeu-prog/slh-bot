import unittest
from unittest.mock import patch

from core import human_intervention as policy
from core import exec_policy


OWNER = "owner-test"


class HumanInterventionTests(unittest.TestCase):
    def setUp(self):
        self.db = {}
        self.load_patch = patch("state_manager.load_db", side_effect=lambda: self.db)
        self.atomic_patch = patch("state_manager.atomic_update", side_effect=self._atomic_update)
        self.owner_policy_patch = patch("core.human_intervention.is_owner", side_effect=lambda uid: str(uid) == OWNER)
        self.owner_exec_patch = patch("core.exec_policy.is_owner", side_effect=lambda uid: str(uid) == OWNER)
        self.rate_patch = patch("core.exec_policy.rate_limit_ok", return_value=True)
        self.load_patch.start()
        self.atomic_patch.start()
        self.owner_policy_patch.start()
        self.owner_exec_patch.start()
        self.rate_patch.start()

    def tearDown(self):
        self.rate_patch.stop()
        self.owner_exec_patch.stop()
        self.owner_policy_patch.stop()
        self.atomic_patch.stop()
        self.load_patch.stop()

    def _atomic_update(self, mutator, *args, **kwargs):
        return mutator(self.db)

    def test_missing_policy_defaults_to_approval_required(self):
        result = policy.get_policy()
        self.assertTrue(result["action_execution"])
        self.assertTrue(result["action_completion"])
        self.assertEqual(result["source"], "default_fail_closed")

    def test_malformed_setting_fails_closed_per_setting(self):
        self.db["human_intervention"] = {
            "settings": {"action_execution": False, "action_completion": "false"}
        }
        result = policy.get_policy()
        self.assertFalse(result["action_execution"])
        self.assertTrue(result["action_completion"])
        self.assertEqual(result["source"], "default_fail_closed")

    def test_non_owner_cannot_create_action(self):
        with self.assertRaises(PermissionError):
            policy.create_execution_request("not-owner", "python3 -c 'print(1)'")

    def test_unclassified_command_waits_without_running(self):
        command = "python3 -c 'print(1)'"
        with patch("core.exec_policy._run") as run:
            ok, output = exec_policy.run_gated(OWNER, command, source="test")
        self.assertFalse(ok)
        self.assertIn("HUMAN_APPROVAL_REQUIRED", output)
        self.assertIn("ID:", output)
        run.assert_not_called()
        state = self.db["human_intervention"]
        record = next(iter(state["requests"].values()))
        self.assertEqual(record["status"], "pending_execution")
        self.assertTrue(state["audit"])
        self.assertFalse(policy.is_read_only_command(command))

    def test_approved_command_runs_once_and_completion_is_separately_gated(self):
        command = "python3 -c 'print(1)'"
        with patch("core.exec_policy._run", return_value=(True, "ok")) as run:
            ok, output = exec_policy.run_gated(OWNER, command, source="test")
            self.assertFalse(ok)
            request_id = output.split("ID: ", 1)[1].splitlines()[0]
            approval = policy.approve_execution(request_id, OWNER)
            self.assertTrue(approval["ok"])
            ok2, output2 = exec_policy.run_gated(
                OWNER, command, source="test-approved",
                intervention_request_id=request_id,
            )
        self.assertTrue(ok2)
        self.assertIn("intervention complete", output2)
        self.assertEqual(run.call_count, 1)
        record = policy.get_request(request_id)
        self.assertEqual(record["status"], "executed_pending_completion")
        self.assertEqual(record["command"], "")
        completed = policy.complete_action(request_id, OWNER)
        self.assertTrue(completed["ok"])
        self.assertEqual(policy.get_request(request_id)["status"], "completed")
        self.assertEqual(policy.complete_action(request_id, OWNER)["error"], "COMPLETION_NOT_PENDING")
        self.assertEqual(run.call_count, 1)

    def test_denied_action_never_runs_and_cannot_be_replayed(self):
        command = "python3 -c 'print(1)'"
        with patch("core.exec_policy._run") as run:
            _, output = exec_policy.run_gated(OWNER, command, source="test")
            request_id = output.split("ID: ", 1)[1].splitlines()[0]
            denied = policy.deny_action(request_id, OWNER)
            self.assertTrue(denied["ok"])
            ok, message = exec_policy.run_gated(
                OWNER, command, source="test",
                intervention_request_id=request_id,
            )
        self.assertFalse(ok)
        self.assertIn("HUMAN_APPROVAL_NOT_VALID", message)
        run.assert_not_called()
        self.assertEqual(policy.get_request(request_id)["status"], "execution_rejected")

    def test_stale_approval_expires_and_cannot_execute(self):
        request = policy.create_execution_request(OWNER, "python3 -c 'print(1)'")
        request_id = request["id"]
        self.db["human_intervention"]["requests"][request_id]["expires_at"] = 0
        result = policy.approve_execution(request_id, OWNER)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "REQUEST_EXPIRED")
        self.assertEqual(policy.get_request(request_id)["status"], "expired")

    def test_setting_disable_requires_explicit_confirmation_and_is_audited(self):
        requested = policy.request_setting_disable(OWNER, "action_execution")
        request_id = requested["request_id"]
        self.assertTrue(policy.get_policy()["action_execution"])
        self.assertTrue(requested["requires_confirmation"])
        wrong_actor = policy.confirm_setting_disable(request_id, "other")
        self.assertEqual(wrong_actor["error"], "OWNER_ONLY")
        confirmed = policy.confirm_setting_disable(request_id, OWNER)
        self.assertTrue(confirmed["ok"])
        self.assertFalse(policy.get_policy()["action_execution"])
        events = self.db["human_intervention"]["audit"]
        self.assertTrue(any(e["decision"] == "disable_requested" for e in events))
        self.assertTrue(any(e["decision"] == "confirmed_disable" for e in events))
        replay = policy.confirm_setting_disable(request_id, OWNER)
        self.assertEqual(replay["error"], "SETTING_REQUEST_NOT_PENDING")

    def test_private_chat_is_required_for_settings_and_approval_commands(self):
        from types import SimpleNamespace
        from handlers.human_intervention_handler import _authorized_private
        with patch("handlers.human_intervention_handler.is_owner", side_effect=lambda uid: str(uid) == OWNER):
            private = SimpleNamespace(chat=SimpleNamespace(type="private"), from_user=SimpleNamespace(id=OWNER))
            group = SimpleNamespace(chat=SimpleNamespace(type="group"), from_user=SimpleNamespace(id=OWNER))
            non_owner = SimpleNamespace(chat=SimpleNamespace(type="private"), from_user=SimpleNamespace(id="other"))
            self.assertTrue(_authorized_private(private))
            self.assertFalse(_authorized_private(group))
            self.assertFalse(_authorized_private(non_owner))

    def test_simple_read_only_command_does_not_create_pending_action(self):
        with patch("core.exec_policy._run", return_value=(True, "/app")) as run:
            ok, output = exec_policy.run_gated(OWNER, "pwd", source="test-read-only")
        self.assertTrue(ok)
        self.assertEqual(output, "/app")
        run.assert_called_once()
        self.assertNotIn("human_intervention", self.db)

    def test_environment_dump_and_private_key_reads_are_not_unattended(self):
        unsafe_reads = (
            "printenv",
            "cat ~/.ssh/id_rsa",
            "cat /root/.ssh/id_ed25519",
            "cat /root/.aws/credentials",
            "grep token /app/config.txt",
        )
        for command in unsafe_reads:
            with self.subTest(command=command):
                self.assertFalse(policy.is_read_only_command(command), command)

        # Each unsafe read must be held for owner approval, never executed now.
        with patch("core.exec_policy._run") as run:
            ok, output = exec_policy.run_gated(OWNER, "printenv", source="test-secret-read")
        self.assertFalse(ok)
        self.assertIn("HUMAN_APPROVAL_REQUIRED", output)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
