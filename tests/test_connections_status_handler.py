import json
import os
import unittest
from unittest.mock import patch

import handlers.connections_status_handler as target


class ConnectionsStatusHandlerTests(unittest.TestCase):
    def test_github_check_blocks_when_token_missing(self):
        with patch.dict(os.environ, {"GIT_TOKEN": "", "GITHUB_TOKEN": ""}):
            self.assertEqual(target._github_check(), ("BLOCKED", "GITHUB_TOKEN_MISSING"))

    def test_github_check_requires_authenticated_identity_and_repository_read(self):
        with patch.dict(os.environ, {"GIT_TOKEN": "test-token"}):
            captured = []

            class Response:
                status = 200
                def __init__(self, data):
                    self.data = data
                def __enter__(self):
                    return self
                def __exit__(self, *_args):
                    return False
                def read(self):
                    return json.dumps(self.data).encode()

            def fake_urlopen(request, timeout):
                captured.append((request.full_url, timeout, request.get_header("Authorization")))
                if request.full_url.endswith("/user"):
                    return Response({"login": "bot-account"})
                return Response({"full_name": "osifeu-prog/slh-bot"})

            with patch.object(target.urllib.request, "urlopen", fake_urlopen):
                self.assertEqual(target._github_check(), ("PASS", "AUTHENTICATED_REPOSITORY_READ_OK"))
            self.assertEqual(len(captured), 2)
            self.assertTrue(captured[0][0].endswith("/user"))
            self.assertTrue(captured[1][0].endswith("/repos/osifeu-prog/slh-bot"))
            self.assertTrue(all(item[1] == 10 for item in captured))
            self.assertTrue(all(item[2] == "Bearer test-token" for item in captured))

    def test_github_check_does_not_expose_http_error_body(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}):
            def fake_urlopen(_request, timeout):
                raise target.urllib.error.HTTPError(
                    "https://api.github.com/user", 401, "Unauthorized", {}, None
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
        with patch.object(target, "_github_check", return_value=("PASS", "AUTHENTICATED_REPOSITORY_READ_OK")), \
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
