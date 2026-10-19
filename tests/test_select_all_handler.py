from unittest.mock import patch

from handlers.select_all_handler import build_select_all_text, register


def test_select_all_returns_copy_friendly_public_guide():
    with patch(
        "handlers.select_all_handler.render_public_help",
        return_value="✨ SLH Spark\n/help — מדריך שימושי",
    ):
        text = build_select_all_text()

    assert "ריכוז תוכן להעתקה" in text
    assert "אינו יכול לקרוא את היסטוריית הצ׳אט" in text
    assert "/help — מדריך שימושי" in text


def test_select_all_registers_one_handler_and_replies():
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
    msg = object()

    with patch(
        "handlers.select_all_handler.build_select_all_text",
        return_value="copy guide",
    ):
        registered["fn"](msg)

    assert registered["kwargs"] == {"commands": ["select_all"]}
    assert bot.reply == (msg, "copy guide")
