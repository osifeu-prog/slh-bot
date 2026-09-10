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


if __name__ == "__main__":
    unittest.main()
