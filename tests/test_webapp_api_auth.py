import unittest
from unittest.mock import patch

import webapp


class WebAppApiAuthTests(unittest.TestCase):
    def setUp(self):
        self.client = webapp.app.test_client()

    def test_global_endpoints_require_telegram_auth(self):
        endpoints = (
            "/api/stats",
            "/api/leaderboard",
            "/api/v1/leaderboard",
            "/api/onchain/status",
        )
        with patch("webapp.authenticated_uid", return_value=None):
            for endpoint in endpoints:
                with self.subTest(endpoint=endpoint):
                    response = self.client.get(endpoint)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.get_json(), {"error": "TELEGRAM_AUTH_REQUIRED"})

    def test_stats_allows_authenticated_user(self):
        db = {
            "users": {"1": {"wallet": {"credits": 10}}},
            "agents": {"a": {}},
            "tasks": {"t": {}},
        }
        with patch("webapp.authenticated_uid", return_value="1"), patch(
            "webapp.load_db", return_value=db
        ):
            response = self.client.get("/api/stats")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "users": 1,
            "agents": 1,
            "tasks": 1,
            "credits": 10,
        })

    def test_wallet_handoff_repeated_get_uses_existing_session_cookie(self):
        token = "handoff-token-for-test-1234567890"
        with patch("core.wallet_handoff.consume_handoff") as consume, patch(
            "core.wallet_handoff.validate_session", return_value="5010371391"
        ):
            response = self.client.get(
                "/wallet-handoff?code="+token+"&next=/slh-smoke",
                headers={"Cookie": "slh_wallet_handoff="+token},
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/slh-smoke")
        consume.assert_not_called()
        self.assertIn("slh_wallet_handoff=", response.headers.get("Set-Cookie", ""))
        self.assertIn("Path=/", response.headers.get("Set-Cookie", ""))


if __name__ == "__main__":
    unittest.main()
