from types import SimpleNamespace
from unittest.mock import patch

from handlers import logo_handler


class FakeBot:
    def __init__(self):
        self.handlers = {}
        self.replies = []

    def message_handler(self, commands=None, **_kwargs):
        def decorator(function):
            for command in commands or []:
                self.handlers[command] = function
            return function
        return decorator

    def reply_to(self, message, text, **kwargs):
        self.replies.append((message, text, kwargs))


def test_logo_command_passes_live_bot_and_requesting_uid():
    bot = FakeBot()
    message = SimpleNamespace(from_user=SimpleNamespace(id=8789977826))
    logo_handler.register_logo_handler(bot)

    with patch.object(logo_handler, "load_branding", return_value="🆔 8789977826") as load:
        bot.handlers["logo"](message)

    load.assert_called_once_with(bot, "8789977826")
    _message, rendered, kwargs = bot.replies[-1]
    assert "8789977826" in rendered
    assert "unknown" not in rendered.lower()
    assert kwargs["parse_mode"] == "HTML"


def test_logo_alias_brand_uses_same_identity_aware_handler():
    bot = FakeBot()
    message = SimpleNamespace(from_user=SimpleNamespace(id=12345))
    logo_handler.register_logo_handler(bot)

    with patch.object(logo_handler, "load_branding", return_value="🆔 12345") as load:
        bot.handlers["brand"](message)

    load.assert_called_once_with(bot, "12345")
