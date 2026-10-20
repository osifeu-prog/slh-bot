import os
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from handlers import staking_handler


class _Bot:
    def __init__(self):
        self.handlers = {}
        self.replies = []

    def message_handler(self, **kwargs):
        def decorator(fn):
            self.handlers[tuple(kwargs.get("commands", []))] = fn
            return fn
        return decorator

    def reply_to(self, message, text, reply_markup=None):
        self.replies.append((message, text, reply_markup))


def test_staking_command_includes_webapp_button_directly_to_stake_screen():
    bot = _Bot()
    message = SimpleNamespace(text="/staking", from_user=SimpleNamespace(id=5010371391))
    target_url = "https://example.test/mini-app-v4?screen=wallet&ref=telegram"

    with patch.dict(os.environ, {"SLH_MINI_APP_URL": target_url}):
        staking_handler.register(bot)
        bot.handlers[("staking",)](message)

    assert len(bot.replies) == 1
    _, reply_text, markup = bot.replies[0]
    assert "Credits נעולים אינם זמינים" in reply_text
    assert "אין הבטחת רווח" in reply_text
    assert markup is not None
    button = markup.keyboard[0][0]
    assert "Staking" in button.text
    parsed = urlsplit(button.web_app.url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "example.test"
    assert parsed.path == "/mini-app-v4"
    query = parse_qs(parsed.query)
    assert query["screen"] == ["stake"]
    assert query["ref"] == ["telegram"]
