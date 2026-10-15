from types import SimpleNamespace
from unittest.mock import patch

import handlers.rewards_handler as rewards_handler


class FakeBot:
    def __init__(self):
        self.handlers = {}
        self.sent = []

    def message_handler(self, commands=None, **kwargs):
        def decorator(fn):
            for command in commands or []:
                self.handlers[command] = fn
            return fn
        return decorator

    def reply_to(self, message, text, **kwargs):
        self.sent.append((message.chat.id, text, kwargs))


def _message(uid=123, text="/daily"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=uid),
        chat=SimpleNamespace(id=uid, type="private"),
        text=text,
    )


def test_daily_handler_reports_points_without_claiming_credits(monkeypatch):
    bot = FakeBot()
    rewards_handler.register(bot)
    monkeypatch.setattr(
        rewards_handler,
        "claim_daily_reward",
        lambda uid: {
            "status": "claimed",
            "points_awarded": 10,
            "streak": 3,
            "points_total": 310,
        },
    )

    bot.handlers["daily"](_message())

    assert len(bot.sent) == 1
    text = bot.sent[0][1]
    assert "+10 Points" in text
    assert "3 ימים" in text
    assert "אינם Credits או SLH" in text


def test_daily_handler_does_not_award_again_for_duplicate(monkeypatch):
    bot = FakeBot()
    rewards_handler.register(bot)
    monkeypatch.setattr(
        rewards_handler,
        "claim_daily_reward",
        lambda uid: {
            "status": "already_claimed",
            "points_awarded": 0,
            "streak": 3,
            "points_total": 310,
        },
    )

    bot.handlers["daily"](_message())

    assert len(bot.sent) == 1
    assert "כבר נרשם היום" in bot.sent[0][1]
    assert "לא יינתן תגמול כפול" in bot.sent[0][1]


def test_daily_handler_returns_safe_message_on_settlement_exception(monkeypatch):
    bot = FakeBot()
    rewards_handler.register(bot)

    def fail(uid):
        raise RuntimeError("internal path details must not be sent to the user")

    monkeypatch.setattr(rewards_handler, "claim_daily_reward", fail)
    with patch("builtins.print"):
        bot.handlers["daily"](_message())

    assert len(bot.sent) == 1
    assert "לא ניתנו Credits או SLH" in bot.sent[0][1]
    assert "internal path details" not in bot.sent[0][1]
