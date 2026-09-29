import unittest
from unittest.mock import patch

import webapp


class CanonicalAiIntakeTests(unittest.TestCase):
    def setUp(self):
        self.client = webapp.app.test_client()
        webapp._AI_RATE_STATE.clear()

    def test_public_intake_uses_canonical_router_without_trusting_user_id(self):
        with patch("core.ask_router.route", return_value="שלום מהמערכת הקנונית") as route:
            response = self.client.post(
                "/api/ai/chat",
                json={"message": "שלום", "user_id": "999999999", "lang": "he"},
                headers={"Origin": "https://slh.co.il"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "reply": "שלום מהמערכת הקנונית",
            "user_id": None,
            "authenticated": False,
        })
        route.assert_called_once_with("שלום", None)

    def test_invalid_telegram_init_data_is_rejected(self):
        with patch(
            "webapp.validate_init_data",
            side_effect=ValueError("TELEGRAM_INIT_DATA_INVALID"),
        ):
            response = self.client.post(
                "/api/ai/chat",
                json={"message": "שלום"},
                headers={
                    "Origin": "https://slh.co.il",
                    "X-Telegram-Init-Data": "tampered",
                },
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json(), {"error": "TELEGRAM_AUTH_INVALID"})

    def test_valid_telegram_init_data_is_the_only_trusted_identity(self):
        with patch(
            "webapp.validate_init_data",
            return_value={"uid": "777", "user": {"id": 777}},
        ), patch(
            "core.ask_router.route",
            return_value="תשובה"
        ) as route:
            response = self.client.post(
                "/api/ai/chat",
                json={"message": "מה היתרה?", "user_id": "888", "lang": "he"},
                headers={
                    "Origin": "https://slh.co.il",
                    "X-Telegram-Init-Data": "valid",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["user_id"], "777")
        self.assertTrue(response.get_json()["authenticated"])
        route.assert_called_once_with("מה היתרה?", "777")

    def test_message_length_is_bounded(self):
        response = self.client.post(
            "/api/ai/chat",
            json={"message": "x" * 4001},
            headers={"Origin": "https://slh.co.il"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "MESSAGE_TOO_LONG"})


if __name__ == "__main__":
    unittest.main()
