import unittest
from types import SimpleNamespace
from unittest.mock import patch

from handlers import advanced_ask_handler


class _Bot:
    def __init__(self):
        self.handlers = []
        self.sent = []

    def message_handler(self, *args, **kwargs):
        def decorator(fn):
            self.handlers.append(fn)
            return fn
        return decorator

    def reply_to(self, msg, text, *args, **kwargs):
        self.sent.append(("reply", text))

    def send_message(self, chat_id, text, *args, **kwargs):
        self.sent.append(("send", text))


class AdvancedAskInputTests(unittest.TestCase):
    def _handler(self):
        bot = _Bot()
        advanced_ask_handler.register_ask_handler(bot)
        self.assertEqual(len(bot.handlers), 1)
        return bot, bot.handlers[0]

    def test_long_question_is_not_silently_truncated(self):
        bot, handler = self._handler()
        question = "x" * 2001
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=100, is_bot=False),
            text="/ask " + question,
            chat=SimpleNamespace(id=123),
            message_id=1,
        )
        captured = {}

        def fake_route(value, uid):
            captured["question"] = value
            captured["uid"] = uid
            return "OK"

        with patch.object(advanced_ask_handler, "route", side_effect=fake_route), patch.object(
            advanced_ask_handler, "is_owner", return_value=False
        ), patch.object(
            advanced_ask_handler, "normalize_keyboard_text", side_effect=lambda value: value
        ):
            handler(message)

        self.assertEqual(len(captured["question"]), 2001)
        self.assertEqual(captured["uid"], "100")
        self.assertEqual(bot.sent[-1], ("send", "OK"))

    def test_over_bound_question_is_rejected_before_route(self):
        bot, handler = self._handler()
        question = "x" * 12001
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=100, is_bot=False),
            text="/ask " + question,
            chat=SimpleNamespace(id=123),
            message_id=1,
        )

        with patch.object(advanced_ask_handler, "route") as route, patch.object(
            advanced_ask_handler, "is_owner", return_value=False
        ), patch.object(
            advanced_ask_handler, "normalize_keyboard_text", side_effect=lambda value: value
        ):
            handler(message)

        route.assert_not_called()
        self.assertIn("12,000", bot.sent[-1][1])


if __name__ == "__main__":
    unittest.main()
