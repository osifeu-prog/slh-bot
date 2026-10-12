from types import SimpleNamespace
from unittest.mock import Mock

import handlers.broadcast_ack_handler as target


def _call(data="ack_seen", uid=12345, chat_type="private"):
    return SimpleNamespace(
        id="callback-1",
        data=data,
        from_user=SimpleNamespace(id=uid, username="tester", first_name="Tester"),
        message=SimpleNamespace(chat=SimpleNamespace(id=uid, type=chat_type)),
    )


def test_ack_is_idempotent_for_repeated_clicks(monkeypatch):
    db = {}
    monkeypatch.setattr(target.state_manager, "atomic_update", lambda mutate: mutate(db))

    first = target._record_ack("12345", "tester", "Tester")
    original = db["broadcast_acks"]["12345"]["first_at"]
    second = target._record_ack("12345", "tester", "Tester")

    assert first["status"] == "ACKED"
    assert second["status"] == "ALREADY_ACKED"
    assert second["total_acks"] == 1
    assert db["broadcast_acks"]["12345"]["count"] == 1
    assert db["broadcast_acks"]["12345"]["first_at"] == original


def test_ack_callback_confirms_once_and_links_to_mini_app(monkeypatch):
    registered = {}

    class Bot:
        callback_query_handler = lambda self, **kwargs: lambda fn: registered.setdefault("callback", fn) or fn
        answer_callback_query = Mock()
        send_message = Mock()

    bot = Bot()
    registered_args = {}

    def decorator(**kwargs):
        registered_args.update(kwargs)
        def wrap(fn):
            registered["callback"] = fn
            return fn
        return wrap

    bot.callback_query_handler = decorator
    monkeypatch.setattr(
        target,
        "_record_ack",
        lambda uid, username, first_name: {"status": "ACKED", "total_acks": 3},
    )
    target.register(bot)

    call = _call()
    registered["callback"](call)

    assert callable(registered_args["func"])
    assert registered_args["func"](call) is True
    bot.answer_callback_query.assert_called_once()
    bot.send_message.assert_called_once_with(
        12345,
        "✅ ראיתי אותך.\n\n"
        "🚀 פתח את ה-Mini App:\n"
        "https://slh-cloud-bot-production.up.railway.app/mini-app-v4",
    )


def test_ack_callback_does_not_record_or_message_groups(monkeypatch):
    registered = {}

    def decorator(**kwargs):
        def wrap(fn):
            registered["callback"] = fn
            return fn
        return wrap

    bot = SimpleNamespace(
        callback_query_handler=decorator,
        answer_callback_query=Mock(),
        send_message=Mock(),
    )
    writes = []
    monkeypatch.setattr(
        target,
        "_record_ack",
        lambda *args: writes.append(args) or {"status": "ACKED", "total_acks": 1},
    )
    target.register(bot)

    call = _call(chat_type="group")
    registered["callback"](call)

    assert writes == []
    bot.answer_callback_query.assert_called_once()
    bot.send_message.assert_not_called()


def test_ack_handler_registers_only_the_exact_callback():
    registered = {}

    def decorator(**kwargs):
        registered["filter"] = kwargs["func"]
        return lambda fn: fn

    bot = SimpleNamespace(callback_query_handler=decorator, answer_callback_query=Mock(), send_message=Mock())
    target.register(bot)

    assert registered["filter"](_call(data="ack_seen")) is True
    assert registered["filter"](_call(data="other")) is False
