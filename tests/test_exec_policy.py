import os
import unittest
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID
from core.exec_policy import (
    _audit_path_allowed,
    is_audit_command,
    is_dangerous,
    redact_secrets,
    run_gated,
    telegram_shell_enabled,
)


class ExecAuditBoundaryTests(unittest.TestCase):
    def test_telegram_shell_is_closed_by_default_without_database_read(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SLH_TELEGRAM_SHELL_ENABLED", None)
            with patch("state_manager.load_db") as load_db, patch("core.exec_policy._run") as runner, patch("core.exec_policy.audit"):
                enabled = telegram_shell_enabled()
                ok, message = run_gated(
                    OWNER_TELEGRAM_ID,
                    "printf shell-probe",
                    source="unit_test",
                )

        self.assertFalse(enabled)
        self.assertFalse(ok)
        self.assertIn("disabled", message.lower())
        load_db.assert_not_called()
        runner.assert_not_called()

    def test_telegram_shell_requires_both_environment_and_database_opt_in(self):
        with patch.dict(os.environ, {"SLH_TELEGRAM_SHELL_ENABLED": "1"}, clear=False):
            with patch("state_manager.load_db", return_value={"security": {"e_command_enabled": False}}):
                self.assertFalse(telegram_shell_enabled())
            with patch("state_manager.load_db", return_value={"security": {"e_command_enabled": True}}):
                self.assertTrue(telegram_shell_enabled())
            with patch("state_manager.load_db", return_value={}):
                self.assertFalse(telegram_shell_enabled())

    def test_run_gated_never_runs_when_database_switch_is_false(self):
        with patch.dict(os.environ, {"SLH_TELEGRAM_SHELL_ENABLED": "1"}, clear=False):
            with patch("state_manager.load_db", return_value={"security": {"e_command_enabled": False}}), patch("core.exec_policy._run") as runner, patch("core.exec_policy.audit"):
                ok, message = run_gated(
                    OWNER_TELEGRAM_ID,
                    "python3 -c 'print(1)'",
                    source="unit_test",
                )

        self.assertFalse(ok)
        self.assertIn("disabled", message.lower())
        runner.assert_not_called()

    def test_run_gated_executes_only_after_both_opt_ins(self):
        with patch.dict(os.environ, {"SLH_TELEGRAM_SHELL_ENABLED": "1"}, clear=False):
            with patch("state_manager.load_db", return_value={"security": {"e_command_enabled": True}}), patch("core.exec_policy._run", return_value=(True, "OK")) as runner:
                ok, message = run_gated(
                    OWNER_TELEGRAM_ID,
                    "printf shell-probe",
                    source="unit_test",
                )

        self.assertTrue(ok)
        self.assertEqual(message, "OK")
        runner.assert_called_once()

    def test_python_is_not_accepted_as_a_read_only_audit_command(self):
        self.assertFalse(is_audit_command("python3 -c 'print(1)'"))
        self.assertFalse(is_audit_command("bash -lc 'id'"))

    def test_allowed_source_reads(self):
        self.assertTrue(is_audit_command("cat core/authority.py"))
        self.assertTrue(is_audit_command("grep -r release core/"))
        self.assertFalse(is_audit_command("grep -R release core/"))
        self.assertTrue(is_audit_command("find handlers/ -type f"))
        self.assertTrue(is_audit_command("sed -n '20,60p' core/exec_policy.py"))
        self.assertTrue(is_audit_command("head -n 30 README.md"))

    def test_direct_credits_mutations_are_blocked(self):
        commands = (
            """python3 -c 'u["credits"] = u.get("credits", 0) + 5'""",
            """python3 -c 'wallet["credits"] += 1'""",
            """python3 -c 'user.credits = 50'""",
            """python3 -c 'wallet.update({"credits": 99})'""",
            """python3 -c 'wallet.setdefault("credits", 0)'""",
        )
        for command in commands:
            self.assertTrue(is_dangerous(command), command)

    def test_reading_credits_is_not_treated_as_a_mutation(self):
        commands = (
            """python3 -c 'print(user["credits"])'""",
            "grep -n credits core/economy_service.py",
            "sed -n '20,60p' core/economy_service.py",
        )
        for command in commands:
            self.assertFalse(is_dangerous(command), command)

    def test_sensitive_runtime_reads_are_blocked(self):
        commands = (
            "cat state/db.json",
            "grep -R token state/",
            "head state/exec_audit.json",
            "find state/ -type f",
            "cat .env",
            "cat .env.example",
            "cat core/.envrc",
            "cat tests/.env-production",
            "grep TOKEN core/.envrc",
            "grep -R secret .git/",
            "grep TOKEN .env",
            "grep TOKEN .env.example",
            "cat core/../.env",
            "awk 'BEGIN {system(\"id\")}'",
            "find handlers/ -exec id \\;",
            "find handlers/ -exec id +",
            "sed -n '1e id' core/exec_policy.py",
        )
        for command in commands:
            self.assertFalse(is_audit_command(command), command)

    def test_unrestricted_root_recursion_is_blocked(self):
        self.assertFalse(is_audit_command("grep -R token ."))
        self.assertFalse(is_audit_command("find . -type f"))

    def test_symlinked_audit_paths_are_blocked(self):
        link = os.path.join("core", ".audit_symlink_regression")
        try:
            os.symlink("../state", link)
            self.assertFalse(_audit_path_allowed(link))
        finally:
            if os.path.islink(link):
                os.unlink(link)

    def test_chaining_remains_blocked(self):
        self.assertFalse(is_audit_command("cat core/authority.py && pwd"))
        self.assertFalse(is_audit_command("grep token core/ | head"))
        self.assertFalse(is_audit_command("find handlers/ -exec id \\;"))
        self.assertFalse(is_audit_command("find handlers/ -exec id +"))
        self.assertFalse(is_audit_command("sed -n '1e id' core/exec_policy.py"))
        self.assertFalse(is_audit_command("awk 'BEGIN {system(\"id\")}'"))

    def test_redacts_credentials_in_json_with_quoted_keys(self):
        password = "device-password-value-123"
        activation = "SLH-ACT-0123456789"
        bridge_token = "bridge-token-value-123456"
        payload = (
            '{"mqtt_password": "' + password + '", '
            '"activation_code": "' + activation + '", '
            '"SLH_MCP_BRIDGE_TOKEN": "' + bridge_token + '"}'
        )

        redacted = redact_secrets(payload)

        for secret in (password, activation, bridge_token):
            self.assertNotIn(secret, redacted)
        self.assertIn('"mqtt_password": "[REDACTED]"', redacted)
        self.assertIn('"activation_code": "[REDACTED]"', redacted)
        self.assertIn('"SLH_MCP_BRIDGE_TOKEN": "[REDACTED]"', redacted)

    def test_redacts_unlabelled_telegram_bot_token(self):
        token = "123456789:ZXABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdef"
        self.assertNotIn(token, redact_secrets("runtime output: " + token))

    def test_redacts_standalone_seed_phrase_and_labelled_mnemonic(self):
        phrase = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima"
        self.assertNotIn(phrase, redact_secrets(phrase))
        labelled = "mnemonic: " + phrase
        self.assertNotIn(phrase, redact_secrets(labelled))


if __name__ == "__main__":
    unittest.main()
