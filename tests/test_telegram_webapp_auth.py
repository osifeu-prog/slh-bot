import hashlib
import hmac
import json
import os
import time
import unittest
from urllib.parse import urlencode
from unittest.mock import patch

from core.telegram_webapp_auth import validate_init_data


class TelegramWebAppAuthTests(unittest.TestCase):
    TOKEN = "123456:TEST_TOKEN"

    def make_init_data(self, auth_date=None, user_id=100, tamper=False):
        auth_date = int(time.time()) if auth_date is None else int(auth_date)
        data = {
            "auth_date": str(auth_date),
            "query_id": "AA-test-query",
            "user": json.dumps({"id": user_id, "first_name": "Test"}, separators=(",", ":")),
        }
        check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
        secret_key = hmac.new(
            b"WebAppData", self.TOKEN.encode(), hashlib.sha256
        ).digest()
        digest = hmac.new(
            secret_key, check_string.encode(), hashlib.sha256
        ).hexdigest()
        if tamper:
            digest = "0" * 64
        data["hash"] = digest
        return urlencode(data)

    @patch.dict(os.environ, {"BOT_TOKEN": TOKEN}, clear=False)
    def test_valid_init_data_returns_authenticated_uid(self):
        result = validate_init_data(self.make_init_data(user_id=777), now=int(time.time()))
        self.assertEqual(result["uid"], "777")

    @patch.dict(os.environ, {"BOT_TOKEN": TOKEN}, clear=False)
    def test_tampered_init_data_rejected(self):
        with self.assertRaisesRegex(ValueError, "TELEGRAM_INIT_DATA_INVALID"):
            validate_init_data(self.make_init_data(tamper=True))

    @patch.dict(os.environ, {"BOT_TOKEN": TOKEN}, clear=False)
    def test_expired_init_data_rejected(self):
        now = int(time.time())
        with self.assertRaisesRegex(ValueError, "TELEGRAM_INIT_DATA_EXPIRED"):
            validate_init_data(self.make_init_data(auth_date=now - 3601), now=now)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_bot_token_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "TELEGRAM_BOT_TOKEN_MISSING"):
            validate_init_data("auth_date=1&hash=x")


if __name__ == "__main__":
    unittest.main()
