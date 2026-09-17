import unittest
from unittest.mock import patch

import handlers.arcade_handler as arcade_handler


class FakeBot:
    def __init__(self):
        self.commands = {}
        self.filters = []
        self.sent = []

    def message_handler(self, commands=None, func=None):
        def decorator(fn):
            for command in commands or []:
                self.commands[command] = fn
            if func is not None:
                self.filters.append((func, fn))
            return fn
        return decorator

    def reply_to(self, msg, text, **kwargs):
        self.sent.append(text)


class Msg:
    def __init__(self, text):
        self.text = text
        self.chat = type("Chat", (), {"id": 100})()
        self.from_user = type("User", (), {"id": 100})()


class ArcadeHandlerTests(unittest.TestCase):
    def setUp(self):
        arcade_handler.arcade_engine.ACTIVE.clear()

    def test_arcade_start_uses_existing_engine(self):
        bot = FakeBot()
        arcade_handler.register(bot)
        with patch.object(
            arcade_handler.arcade_engine,
            "start_game",
            return_value={"status": "started", "question": "2 + 2 = ?", "deadline": 160},
        ) as start:
            bot.commands["arcade"](Msg("/arcade"))

        start.assert_called_once_with("100")
        self.assertIn("2 + 2 = ?", bot.sent[-1])

    def test_active_answer_uses_existing_engine(self):
        bot = FakeBot()
        arcade_handler.register(bot)
        arcade_handler.arcade_engine.ACTIVE["100"] = {"question": "2 + 2 = ?"}
        with patch.object(
            arcade_handler.arcade_engine,
            "answer_game",
            return_value={"status": "answered", "correct": True, "score": 1, "question": "3 - 1 = ?"},
        ) as answer:
            for predicate, fn in bot.filters:
                if predicate(Msg("2")):
                    fn(Msg("2"))
                    break

        answer.assert_called_once_with("100", "2")
        self.assertIn("3 - 1 = ?", bot.sent[-1])


if __name__ == "__main__":
    unittest.main()
