from types import SimpleNamespace
from unittest.mock import Mock

import handlers.broadcast_ack_handler as target


def _registered_handler():
    registered = {}

    class Bot:
        answer_callback_query = Mock()
        send_message = Mock()

        def callback_query_handler(self, **kwargs):
            registered["filter"] = kwargs["func"]

            def decorate(fn):
                registered["handler"] = fn
                return fn

            return decorate

    bot = Bot()
    target.register(bot)
    return bot, registered


def test_ack_callback_records_and_confirms_seen(monkeypatch):
    bot, registered = _registered_handler()
    saved = []
    monkeypatch.setattr(
        target,
        "_record_ack",
        lambda uid, username, first_name: saved.append(
            (uid, username, first_name)
        ) or {"ok": True, "total_acks": 1},
    )
    call = SimpleNamespace(
        data="ack_seen",
        id="callback-1",
        from_user=SimpleNamespace(id=12345, username="member", first_name="Member"),
        message=SimpleNamespace(chat=SimpleNamespace(id=12345)),
    )

    assert registered["filter"](call) is True
    registered["handler"](call)

    assert saved == [("12345", "member", "Member")]
    bot.answer_callback_query.assert_called_once_with("callback-1", '✅ תודה! נרשמת (1 סה"כ)')
    bot.send_message.assert_called_once()
    assert bot.send_message.call_args.args[0] == 12345
    assert "mini-app-v4" in bot.send_message.call_args.args[1]


def test_ack_callback_ignores_unrelated_callbacks():
    _, registered = _registered_handler()
    unrelated = SimpleNamespace(data="not_ack_seen")

    assert registered["filter"](unrelated) is False
