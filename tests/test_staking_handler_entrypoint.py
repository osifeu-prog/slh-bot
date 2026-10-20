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
        self.sent = []
        self.answered_callbacks = []
        self.edited_markups = []

    def message_handler(self, **kwargs):
        def decorator(fn):
            self.handlers[tuple(kwargs.get("commands", []))] = fn
            return fn
        return decorator

    def callback_query_handler(self, **kwargs):
        def decorator(fn):
            self.callback_handlers.append((kwargs, fn))
            return fn
        return decorator

    def reply_to(self, message, text, reply_markup=None):
        self.replies.append((message, text, reply_markup))

    def answer_callback_query(self, callback_id, text=None):
        self.answered_callbacks.append((callback_id, text))

    def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))

    def edit_message_reply_markup(self, chat_id, message_id, reply_markup=None):
        self.edited_markups.append((chat_id, message_id, reply_markup))


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


def _invoke_staking_callback(bot, call):
    for options, handler in bot.callback_handlers:
        if options["func"](call):
            handler(call)
            return
    raise AssertionError("No staking callback handler matched")


def test_stake_command_previews_lock_and_does_not_move_credits_before_confirmation():
    bot = _Bot()
    message = SimpleNamespace(text="/stake 25", from_user=SimpleNamespace(id=5010371391))
    staking_handler._PENDING_STAKES.clear()

    with patch("handlers.staking_handler.staking_service.stake_locked") as stake_locked:
        staking_handler.register(bot)
        bot.handlers[("stake",)](message)

    assert len(bot.replies) == 1
    _, text, markup = bot.replies[0]
    assert "25 Credits" in text
    assert "30 ימים" in text
    assert "מועד שחרור משוער" in text
    assert "תגמול אינו מובטח" in text
    assert markup is not None
    assert markup.keyboard[0][0].text == "✅ אשר נעילה"
    assert markup.keyboard[0][1].text == "✖️ ביטול"
    stake_locked.assert_not_called()


def test_stake_confirmation_binds_to_user_and_uses_idempotency_key():
    bot = _Bot()
    message = SimpleNamespace(text="/stake_lock 12 14", from_user=SimpleNamespace(id=5010371391))
    staking_handler._PENDING_STAKES.clear()
    position = {
        "id": "sp_test123",
        "unlocks_at": 1790000000,
    }

    with patch(
        "handlers.staking_handler.staking_service.stake_locked",
        return_value={"status": "completed", "credits": 88, "staked": 12, "position": position},
    ) as stake_locked:
        staking_handler.register(bot)
        bot.handlers[("stake_lock",)](message)
        _, preview, markup = bot.replies[-1]
        assert "14 ימים" in preview
        assert "12 Credits" in preview
        token = markup.keyboard[0][0].callback_data.split(":", 1)[1]
        call = SimpleNamespace(
            id="callback-1",
            data=f"slh_stake_confirm:{token}",
            from_user=SimpleNamespace(id=5010371391),
            message=SimpleNamespace(chat=SimpleNamespace(id=5010371391), message_id=55),
        )
        _invoke_staking_callback(bot, call)

    stake_locked.assert_called_once()
    args = stake_locked.call_args
    assert args.args[:2] == ("5010371391", 12)
    assert args.kwargs["lock_days"] == 14
    assert args.kwargs["request_id"] == f"telegram-stake-confirm:{token}"
    assert args.kwargs["meta"]["confirmed_via"] == "inline_button"
    assert bot.sent and "מועד שחרור:" in bot.sent[-1][1]
    assert "תגמול אינו מובטח" in bot.sent[-1][1]


def test_stake_confirmation_from_another_user_does_not_mutate_account():
    bot = _Bot()
    message = SimpleNamespace(text="/stake 5", from_user=SimpleNamespace(id=5010371391))
    staking_handler._PENDING_STAKES.clear()

    with patch("handlers.staking_handler.staking_service.stake_locked") as stake_locked:
        staking_handler.register(bot)
        bot.handlers[("stake",)](message)
        _, _, markup = bot.replies[-1]
        token = markup.keyboard[0][0].callback_data.split(":", 1)[1]
        forged = SimpleNamespace(
            id="callback-forged",
            data=f"slh_stake_confirm:{token}",
            from_user=SimpleNamespace(id=123456789),
            message=SimpleNamespace(chat=SimpleNamespace(id=123456789), message_id=56),
        )
        _invoke_staking_callback(bot, forged)

    stake_locked.assert_not_called()
    assert bot.answered_callbacks
    assert "שייך" in bot.answered_callbacks[-1][1]


def test_stake_cancel_clears_pending_confirmation_without_mutation():
    bot = _Bot()
    message = SimpleNamespace(text="/stake 5", from_user=SimpleNamespace(id=5010371391))
    staking_handler._PENDING_STAKES.clear()

    with patch("handlers.staking_handler.staking_service.stake_locked") as stake_locked:
        staking_handler.register(bot)
        bot.handlers[("stake",)](message)
        _, _, markup = bot.replies[-1]
        token = markup.keyboard[0][1].callback_data.split(":", 1)[1]
        call = SimpleNamespace(
            id="callback-cancel",
            data=f"slh_stake_cancel:{token}",
            from_user=SimpleNamespace(id=5010371391),
            message=SimpleNamespace(chat=SimpleNamespace(id=5010371391), message_id=57),
        )
        _invoke_staking_callback(bot, call)

    stake_locked.assert_not_called()
    assert token not in staking_handler._PENDING_STAKES
    assert "לא בוצע שינוי" in bot.answered_callbacks[-1][1]
