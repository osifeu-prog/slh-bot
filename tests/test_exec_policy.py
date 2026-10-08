import unittest

from core.exec_policy import is_audit_command


class ExecAuditBoundaryTests(unittest.TestCase):
    def test_allowed_source_reads(self):
        self.assertTrue(is_audit_command("cat core/authority.py"))
        self.assertTrue(is_audit_command("grep -R release readiness core/"))
        self.assertTrue(is_audit_command("find handlers/ -type f"))

    def test_sensitive_runtime_reads_are_blocked(self):
        commands = (
            "cat state/db.json",
            "grep -R token state/",
            "head state/exec_audit.json",
            "find state/ -type f",
            "cat .env",
            "cat .env.example",
            "grep -R secret .git/",
        )
        for command in commands:
            self.assertFalse(is_audit_command(command), command)

    def test_unrestricted_root_recursion_is_blocked(self):
        self.assertFalse(is_audit_command("grep -R token ."))
        self.assertFalse(is_audit_command("find . -type f"))

    def test_chaining_remains_blocked(self):
        self.assertFalse(is_audit_command("cat core/authority.py && pwd"))
        self.assertFalse(is_audit_command("grep token core/ | head"))


if __name__ == "__main__":
    unittest.main()
