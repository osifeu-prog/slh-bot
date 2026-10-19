from types import SimpleNamespace
from unittest.mock import patch

from handlers.select_all_handler import build_select_all_text, register


def test_select_all_returns_copy_friendly_public_guide():
    with patch(
        "handlers.select_all_handler.render_public_help",
        return_value="✨ SLH Spark\n/help — מדריך שימושי",
    ):
        text = build_select_all_text()

    assert "ריכוז תוכן להעתקה" in text
    assert "הבוט אינו יכול לסמן או לבחור הודעות" in text
    assert "/help — מדריך שימושי" in text


def _registered_handler():
    registered = {}

    class FakeBot:
        def message_handler(self, **kwargs):
            def decorator(fn):
                registered.update(kwargs=kwargs, fn=fn)
                return fn
            return decorator

        def reply_to(self, msg, text):
            self.reply = (msg, text)

    bot = FakeBot()
    register(bot)
    return bot, registered


def test_select_all_registers_both_aliases_and_handles_space_syntax():
    bot, registered = _registered_handler()
    msg = SimpleNamespace(text="/select all")

    with patch(
        "handlers.select_all_handler.build_select_all_text",
        return_value="copy guide",
    ):
        registered["fn"](msg)

    assert registered["kwargs"] == {"commands": ["select_all", "select"]}
    assert bot.reply == (msg, "copy guide")


def test_select_without_all_argument_shows_usage():
    bot, registered = _registered_handler()
    msg = SimpleNamespace(text="/select")

    registered["fn"](msg)

    assert bot.reply[0] is msg
    assert "/select all" in bot.reply[1]
    assert "מדריך פקודות" in bot.reply[1]


def test_select_all_underscore_alias_still_returns_guide():
    bot, registered = _registered_handler()
    msg = SimpleNamespace(text="/select_all@Me_ad_main_bot")

    with patch(
        "handlers.select_all_handler.build_select_all_text",
        return_value="copy guide",
    ):
        registered["fn"](msg)

    assert bot.reply == (msg, "copy guide")
