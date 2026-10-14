import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from handlers import exchange_handler


class FakeBot:
    def __init__(self):
        self.registered = []
        self.replies = []

    def message_handler(self, *args, **kwargs):
        def decorator(fn):
            self.registered.append({"options": kwargs, "handler": fn})
            return fn
        return decorator

    def reply_to(self, message, text, **kwargs):
        self.replies.append({"message": message, "text": text, **kwargs})


class ChartCommandTests(unittest.TestCase):
    def _chart_handler(self, bot):
        exchange_handler.register(bot)
        matches = [
            item["handler"] for item in bot.registered
            if "chart" in item["options"].get("commands", [])
        ]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_chart_command_opens_exchange_and_preserves_configured_query(self):
        bot = FakeBot()
        command = self._chart_handler(bot)
        message = SimpleNamespace(text="/chart", from_user=SimpleNamespace(id=123), chat=SimpleNamespace(type="private"))
        with patch.dict(os.environ, {
            "SLH_MINI_APP_URL": "https://example.test/mini-app-v4?lang=he&screen=wallet"
        }):
            command(message)

        self.assertEqual(len(bot.replies), 1)
        reply = bot.replies[0]
        self.assertIn("מסחר פנימי ב־SLH", reply["text"])
        self.assertEqual(reply["parse_mode"], "HTML")
        markup = reply["reply_markup"]
        button = markup.keyboard[0][0]
        self.assertEqual(button.text, "📈 פתח גרף מחיר")
        parts = urlsplit(button.web_app.url)
        self.assertEqual(parts.scheme, "https")
        self.assertEqual(parts.netloc, "example.test")
        self.assertEqual(parse_qs(parts.query), {"lang": ["he"], "screen": ["exchange"]})

    def test_chart_command_uses_secure_default_when_url_is_not_configured(self):
        bot = FakeBot()
        command = self._chart_handler(bot)
        message = SimpleNamespace(text="/chart", from_user=SimpleNamespace(id=123), chat=SimpleNamespace(type="private"))
        with patch.dict(os.environ, {}, clear=True):
            command(message)

        self.assertEqual(len(bot.replies), 1)
        reply = bot.replies[0]
        button = reply["reply_markup"].keyboard[0][0]
        self.assertEqual(
            button.web_app.url,
            "https://slh-cloud-bot-production.up.railway.app/mini-app-v4?screen=exchange",
        )

    def test_chart_command_fails_closed_for_non_https_url(self):
        bot = FakeBot()
        command = self._chart_handler(bot)
        message = SimpleNamespace(text="/chart", from_user=SimpleNamespace(id=123), chat=SimpleNamespace(type="private"))
        with patch.dict(os.environ, {"SLH_MINI_APP_URL": "http://example.test/mini-app-v4"}):
            command(message)

        self.assertEqual(len(bot.replies), 1)
        self.assertIn("לא ניתן להכין קישור מאובטח", bot.replies[0]["text"])
        self.assertNotIn("reply_markup", bot.replies[0])


if __name__ == "__main__":
    unittest.main()
