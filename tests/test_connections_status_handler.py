import json
import os
import unittest
from unittest.mock import patch

import handlers.connections_status_handler as target


class ConnectionsStatusHandlerTests(unittest.TestCase):
    def test_github_check_blocks_when_token_missing(self):
        with patch.dict(os.environ, {"GIT_TOKEN": "", "GITHUB_TOKEN": ""}):
            self.assertEqual(target._github_check(), ("BLOCKED", "GITHUB_TOKEN_MISSING"))

    def test_github_check_passes_only_for_expected_repository(self):
        with patch.dict(os.environ, {"GIT_TOKEN": "test-token"}):
            class Response:
                status = 200
                def __enter__(self):
                    return self
                def __exit__(self, *_args):
                    return False
                def read(self):
                    return json.dumps({"full_name": "osifeu-prog/slh-bot"}).encode()

            captured = {}
            def fake_urlopen(request, timeout):
                captured["url"] = request.full_url
                captured["timeout"] = timeout
                captured["authorization"] = request.get_header("Authorization")
                return Response()

            with patch.object(target.urllib.request, "urlopen", fake_urlopen):
                self.assertEqual(target._github_check(), ("PASS", "REPOSITORY_READ_OK"))
            self.assertTrue(captured["url"].endswith("/repos/osifeu-prog/slh-bot"))
            self.assertEqual(captured["timeout"], 10)
            self.assertEqual(captured["authorization"], "Bearer test-token")

    def test_github_check_does_not_expose_http_error_body(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}):
            def fake_urlopen(_request, timeout):
                raise target.urllib.error.HTTPError(
                    "https://api.github.com/repos/osifeu-prog/slh-bot",
                    401, "Unauthorized", {}, None
                )
            with patch.object(target.urllib.request, "urlopen", fake_urlopen):
                self.assertEqual(target._github_check(), ("BLOCKED", "GITHUB_HTTP_401"))

    def test_railway_check_reports_missing_explicit_token_without_secret(self):
        env = {
            "SLH_RAILWAY_TOKEN": "",
            "SLH_RAILWAY_PROJECT_ID": "project",
            "SLH_RAILWAY_ENVIRONMENT_ID": "environment",
            "SLH_RAILWAY_SERVICE_ID": "service",
        }
        with patch.dict(os.environ, env):
            status, reason = target._railway_check()
        self.assertEqual(status, "BLOCKED")
        self.assertEqual(reason, "SLH_RAILWAY_CREDENTIALS_MISSING")

    def test_status_is_read_only_and_contains_timestamp(self):
        with patch.object(target, "_github_check", return_value=("PASS", "REPOSITORY_READ_OK")), \
             patch.object(target, "_railway_check", return_value=("BLOCKED", "SLH_RAILWAY_CREDENTIALS_MISSING")):
            result = target.connections_status_text()
        self.assertIn("Overall: ATTENTION", result)
        self.assertIn("GitHub: PASS", result)
        self.assertIn("Railway: BLOCKED", result)
        self.assertIn("Checked at (UTC):", result)
        self.assertIn("No secrets displayed", result)
        self.assertIn("No provider settings, deployments, balances, or ledgers changed.", result)


if __name__ == "__main__":
    unittest.main()
