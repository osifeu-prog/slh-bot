import unittest

from core.exec_policy import is_audit_command, is_dangerous, redact_secrets


class ExecAuditBoundaryTests(unittest.TestCase):
    def test_allowed_source_reads(self):
        self.assertTrue(is_audit_command("cat core/authority.py"))
        self.assertTrue(is_audit_command("grep -R release core/"))
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
