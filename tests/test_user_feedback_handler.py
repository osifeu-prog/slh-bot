from types import SimpleNamespace
from unittest.mock import Mock

import handlers.user_feedback_handler as target


def _message(text, uid=12345):
    return SimpleNamespace(
        text=text,
        from_user=SimpleNamespace(id=uid, username="tester", first_name="Tester"),
        chat=SimpleNamespace(type="private", id=uid),
    )


def _register_capture():
    registered = {}

    class Bot:
        def message_handler(self, **kwargs):
            registered["kwargs"] = kwargs

            def decorate(fn):
                registered["callback"] = fn
                return fn

            return decorate

        reply_to = Mock()
        send_message = Mock()

    bot = Bot()
    target.register(bot)
    return bot, registered


def test_feedback_handler_is_opt_in_and_does_not_capture_general_chat():
    bot, registered = _register_capture()

    assert set(registered["kwargs"]["commands"]) == {"bugreport", "suggest"}
    assert "func" not in registered["kwargs"]
    assert registered["kwargs"]["content_types"] == ["text"]
    assert bot.send_message.call_count == 0


def test_bugreport_records_and_notifies_owner(monkeypatch):
    bot, registered = _register_capture()
    recorded = []
    notified = []
    monkeypatch.setattr(
        target,
        "_record",
        lambda uid, username, first_name, text, category: recorded.append(
            (uid, username, first_name, text, category)
        ) or {"id": 7},
    )
    monkeypatch.setattr(
        target,
        "_notify_owner",
        lambda *args: notified.append(args),
    )
    message = _message("/bugreport I cannot see Exchange")

    registered["callback"](message)

    assert recorded == [("12345", "tester", "Tester", "I cannot see Exchange", "bug")]
    assert len(notified) == 1
    bot.reply_to.assert_called_once()
    assert "תודה" in bot.reply_to.call_args.args[1]


def test_suggest_uses_feature_category(monkeypatch):
    bot, registered = _register_capture()
    recorded = []
    monkeypatch.setattr(
        target,
        "_record",
        lambda uid, username, first_name, text, category: recorded.append(category) or {"id": 8},
    )
    monkeypatch.setattr(target, "_notify_owner", lambda *args: None)
    registered["callback"](_message("/suggest Add a one-tap voting button"))

    assert recorded == ["feature"]


def test_empty_bugreport_prompts_for_details_without_writing(monkeypatch):
    bot, registered = _register_capture()
    monkeypatch.setattr(
        target,
        "_record",
        lambda *args: (_ for _ in ()).throw(AssertionError("must not write an empty report")),
    )
    registered["callback"](_message("/bugreport"))

    bot.reply_to.assert_called_once()
    assert "/bugreport" in bot.reply_to.call_args.args[1]


def test_owner_notification_has_real_newlines(monkeypatch):
    class NotifyBot:
        def __init__(self):
            self.sent = []

        def send_message(self, uid, text):
            self.sent.append((uid, text))

    bot = NotifyBot()
    monkeypatch.setattr(target, "OWNER_UID", "8789977826")
    target._notify_owner(bot, "12345", "Tester", "tester", "The button is broken", "bug", 4)

    assert len(bot.sent) == 1
    body = bot.sent[0][1]
    assert "\\n" not in body
    assert "\n" in body
