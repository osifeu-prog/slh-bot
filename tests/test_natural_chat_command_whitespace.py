from types import SimpleNamespace
from unittest.mock import patch

import handlers.natural_chat as natural_chat


class FakeBot:
    def __init__(self):
        self.handler = None
        self.sent = []

    def message_handler(self, **kwargs):
        def decorator(fn):
            self.handler = fn
            return fn
        return decorator

    def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))

    def send_chat_action(self, chat_id, action):
        raise AssertionError("whitespace-prefixed command must not call the LLM path")


def _message(text):
    return SimpleNamespace(
        text=text,
        from_user=SimpleNamespace(id=8789977826, is_bot=False),
        chat=SimpleNamespace(id=8789977826, type="private"),
    )


def test_leading_whitespace_command_is_not_routed_to_llm():
    bot = FakeBot()
    natural_chat.register(bot)

    with patch.object(
        natural_chat, "route",
        side_effect=AssertionError("command text must never be sent to the LLM"),
    ):
        bot.handler(_message("   /exchange_gate status"))

    assert len(bot.sent) == 1
    assert "שלח שוב" in bot.sent[0][1]
    assert "רווחים" in bot.sent[0][1]


def test_plain_natural_text_is_not_mislabeled_as_a_command():
    bot = FakeBot()
    natural_chat.register(bot)
    with patch.object(natural_chat, "route", return_value="תשובה") as route:
        bot.handler(_message("מה מצב המערכת?"))
    route.assert_called_once_with("מה מצב המערכת?", "8789977826")
    assert bot.sent[-1][1] == "תשובה"
