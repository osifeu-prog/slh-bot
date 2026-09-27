import os
import unittest

from core.developer_lab import can_propose_path, submit_proposal


class DeveloperLabSafetyTests(unittest.TestCase):
    def test_allowed_source_paths(self):
        self.assertTrue(can_propose_path("handlers/example.py"))
        self.assertTrue(can_propose_path("core/example.py"))
        self.assertTrue(can_propose_path("tests/test_example.py"))
        self.assertTrue(can_propose_path("mini_app.html"))

    def test_protected_paths(self):
        self.assertFalse(can_propose_path("core/authority.py"))
        self.assertFalse(can_propose_path("core/bnb_gate.py"))
        self.assertFalse(can_propose_path(".github/workflows/ci.yml"))
        self.assertFalse(can_propose_path("state/db.json"))

    def test_secret_content_is_rejected(self):
        old = os.environ.get("SLH_GITHUB_REPOSITORY")
        try:
            os.environ["SLH_GITHUB_REPOSITORY"] = "osifeu-prog/slh-bot"
            with self.assertRaises(ValueError) as ctx:
                submit_proposal(
                    "0",
                    "handlers/example.py",
                    "BOT_TOKEN=12345678:AAabcdefghijklmnopqrstuvwxyz123456",
                    "test",
                )
            self.assertEqual(str(ctx.exception), "SECRET_CONTENT_BLOCKED")
        finally:
            if old is None:
                os.environ.pop("SLH_GITHUB_REPOSITORY", None)
            else:
                os.environ["SLH_GITHUB_REPOSITORY"] = old


if __name__ == "__main__":
    unittest.main()
