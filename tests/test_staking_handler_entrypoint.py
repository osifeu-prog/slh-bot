import os
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from handlers import staking_handler


class _Bot:
    def __init__(self):
        self.handlers = {}
        self.callback_handlers = []
        self.replies = []
        self.callback_answers = []

    def message_handler(self, **kwargs):
        def decorator(fn):
            self.handlers[tuple(kwargs.get("commands", []))] = fn
            return fn
        return decorator

    def callback_query_handler(self, **kwargs):
        def decorator(fn):
            self.callback_handlers.append((kwargs.get("func"), fn))
            return fn
        return decorator

    def answer_callback_query(self, call_id, text=None, show_alert=False):
        self.callback_answers.append((call_id, text, show_alert))

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



def test_stake_command_previews_terms_and_does_not_mutate_before_confirmation():
    bot = _Bot()
    message = SimpleNamespace(text="/stake 25", from_user=SimpleNamespace(id=5010371391))

    with patch.object(staking_handler.staking_service, "stake_locked") as stake_locked:
        staking_handler.register(bot)
        bot.handlers[("stake",)](message)

    stake_locked.assert_not_called()
    assert len(bot.replies) == 1
    _, reply_text, markup = bot.replies[0]
    assert "25 Credits" in reply_text
    assert "30 ימים" in reply_text
    assert "מועד שחרור משוער" in reply_text
    assert "אין תשואה קבועה או מובטחת" in reply_text
    assert "לא בוצע שינוי ביתרה" in reply_text
    assert markup is not None
    buttons = markup.keyboard[0]
    assert buttons[0].callback_data.startswith("ss:c:5010371391:25:30:")
    assert buttons[1].callback_data.startswith("ss:x:5010371391:25:30:")


def test_stake_confirmation_executes_only_for_owner_and_uses_idempotency_key():
    import time

    bot = _Bot()
    message = SimpleNamespace(text="/stake 25", from_user=SimpleNamespace(id=5010371391))
    staking_handler.register(bot)
    callback_handler = bot.callback_handlers[0][1]
    issued_at_ms = int(time.time() * 1000)
    call = SimpleNamespace(
        id="callback-1",
        data=f"ss:c:5010371391:25:30:{issued_at_ms}",
        from_user=SimpleNamespace(id=5010371391),
        message=message,
    )
    result = {
        "status": "completed",
        "position": {"id": "sp_test", "unlocks_at": time.time() + 30 * 86400},
        "credits": 75,
        "staked": 25,
    }

    with patch.object(staking_handler.staking_service, "stake_locked", return_value=result) as stake_locked:
        callback_handler(call)

    stake_locked.assert_called_once()
    args = stake_locked.call_args
    assert args.args[:2] == ("5010371391", 25)
    assert args.kwargs["lock_days"] == 30
    assert args.kwargs["request_id"] == f"telegram-stake-5010371391-{issued_at_ms}"
    assert "נעילת Credits הושלמה" in bot.replies[-1][1]
    assert "Position: sp_test" in bot.replies[-1][1]


def test_stake_confirmation_rejects_other_user_without_mutation():
    import time

    bot = _Bot()
    message = SimpleNamespace(text="/stake 25", from_user=SimpleNamespace(id=5010371391))
    staking_handler.register(bot)
    callback_handler = bot.callback_handlers[0][1]
    issued_at_ms = int(time.time() * 1000)
    call = SimpleNamespace(
        id="callback-2",
        data=f"ss:c:5010371391:25:30:{issued_at_ms}",
        from_user=SimpleNamespace(id=5010371392),
        message=message,
    )

    with patch.object(staking_handler.staking_service, "stake_locked") as stake_locked:
        callback_handler(call)

    stake_locked.assert_not_called()
    assert bot.callback_answers[-1][2] is True
    assert "משתמש אחר" in bot.callback_answers[-1][1]
