import types

import handlers.broadcast_handler as target


class FakeBot:
    def __init__(self, scripted=None):
        self.scripted = list(scripted or [])
        self.sent = []
        self.replies = []

    def message_handler(self, commands):
        def decorator(fn):
            self.broadcast_cmd = fn
            return fn
        return decorator

    def send_message(self, uid, message):
        self.sent.append((uid, message))
        if self.scripted:
            action = self.scripted.pop(0)
            if isinstance(action, Exception):
                raise action

    def reply_to(self, message, text):
        self.replies.append((message, text))


def test_retry_after_parsing():
    class RateLimitedError(Exception):
        def __init__(self):
            self.result_json = {"parameters": {"retry_after": 7}}

    assert target._retry_after_seconds(RateLimitedError()) == 7.0


def test_broadcast_is_paced_and_owner_only(monkeypatch):
    bot = FakeBot()
    target.register(bot)

    clock = iter([0.0, 0.01, 0.05, 0.06, 0.10, 0.11])
    sleeps = []
    monkeypatch.setattr(target.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(target.time, "sleep", lambda value: sleeps.append(value))
    monkeypatch.setattr(
        target.state_manager,
        "load_db",
        lambda: {"users": {"1": {}, "2": {}}},
    )

    owner_message = types.SimpleNamespace(
        from_user=types.SimpleNamespace(id=target.OWNER_TELEGRAM_ID),
        text="/broadcast hello",
    )
    bot.broadcast_cmd(owner_message)

    assert bot.sent == [("1", "hello"), ("2", "hello")]
    assert any(value > 0 for value in sleeps)
    assert bot.replies[-1][1] == "✅ Broadcast sent to 2 users.\nFailed: 0"


def test_non_owner_is_rejected(monkeypatch):
    bot = FakeBot()
    target.register(bot)

    loaded = []
    monkeypatch.setattr(
        target.state_manager,
        "load_db",
        lambda: loaded.append(True) or {"users": {}},
    )

    message = types.SimpleNamespace(
        from_user=types.SimpleNamespace(id=12345),
        text="/broadcast hello",
    )
    bot.broadcast_cmd(message)

    assert bot.replies == [(message, "⛔ OWNER only")]
    assert loaded == []


def test_exchange_status_claim_is_refused_by_generic_broadcast(monkeypatch):
    bot = FakeBot()
    target.register(bot)

    loaded = []
    monkeypatch.setattr(
        target.state_manager,
        "load_db",
        lambda: loaded.append(True) or {"users": {"1": {}}},
    )
    message = types.SimpleNamespace(
        from_user=types.SimpleNamespace(id=target.OWNER_TELEGRAM_ID),
        text="/broadcast 🟢 SLH OS — המסחר הפנימי פתוח",
    )

    bot.broadcast_cmd(message)

    assert bot.sent == []
    assert loaded == []
    assert len(bot.replies) == 1
    assert "קולי" in bot.replies[0][1]
