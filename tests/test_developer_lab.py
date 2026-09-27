import os
import unittest
from unittest.mock import patch

import core.developer_lab as developer_lab


class DeveloperLabSafetyTests(unittest.TestCase):
    def test_allowed_source_paths(self):
        self.assertTrue(developer_lab.can_propose_path("handlers/example.py"))
        self.assertTrue(developer_lab.can_propose_path("core/example.py"))
        self.assertTrue(developer_lab.can_propose_path("tests/test_example.py"))
        self.assertTrue(developer_lab.can_propose_path("mini_app.html"))

    def test_protected_paths(self):
        self.assertFalse(developer_lab.can_propose_path("core/authority.py"))
        self.assertFalse(developer_lab.can_propose_path("core/bnb_gate.py"))
        self.assertFalse(developer_lab.can_propose_path(".github/workflows/ci.yml"))
        self.assertFalse(developer_lab.can_propose_path("state/db.json"))

    def test_secret_content_is_rejected(self):
        old = os.environ.get("SLH_GITHUB_REPOSITORY")
        try:
            os.environ["SLH_GITHUB_REPOSITORY"] = "osifeu-prog/slh-bot"
            with patch.object(developer_lab, "get_role", return_value="DEVELOPER"):
                with self.assertRaises(ValueError) as ctx:
                    developer_lab.submit_proposal(
                        "123456789",
                        "handlers/example.py",
                        "BOT_TOKEN=12345678:AA" + "a" * 32,
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
