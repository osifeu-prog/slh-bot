import unittest
from types import SimpleNamespace
from unittest.mock import patch

from handlers import bot_system_control_handler


class FakeBot:
    def __init__(self):
        self.handlers = {}
        self.sent = []

    def message_handler(self, commands=None, **_):
        def deco(fn):
            for command in commands or []:
                self.handlers[command] = fn
            return fn
        return deco

    def reply_to(self, message, text):
        self.sent.append(text)


class BotSystemControlHandlerTests(unittest.TestCase):
    def test_registers_owner_commands(self):
        bot = FakeBot()
        with patch.object(bot_system_control_handler, "is_owner", return_value=True),              patch.object(bot_system_control_handler, "report", return_value="CENTRAL"):
            bot_system_control_handler.register(bot)
            message = SimpleNamespace(from_user=SimpleNamespace(id=1))
            bot.handlers["bots"](message)
        self.assertEqual(bot.sent[-1], "CENTRAL")
        self.assertIn("botcontrol", bot.handlers)


if __name__ == "__main__":
    unittest.main()
