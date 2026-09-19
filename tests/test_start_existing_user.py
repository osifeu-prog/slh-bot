"""Regression test for existing-user /start routing.

The test is isolated and never touches production Telegram or state.
"""

import importlib
import types


class FakeBot:
    def __init__(self):
        self.handlers = []
        self.messages = []

    def message_handler(self, **kwargs):
        def decorator(fn):
            self.handlers.append(("message", kwargs, fn))
            return fn
        return decorator

    def callback_query_handler(self, **kwargs):
        def decorator(fn):
            self.handlers.append(("callback", kwargs, fn))
            return fn
        return decorator

    def send_message(self, chat_id, text, **kwargs):
        self.messages.append({"chat_id": chat_id, "text": text, **kwargs})

    def get_me(self):
        return types.SimpleNamespace(username="TestBot")


def test_existing_user_start_opens_dashboard(monkeypatch):
    import handlers.onboarding_v2 as onboarding
    onboarding = importlib.reload(onboarding)

    uid = "123456789"
    db = {
        "users": {
            uid: {
                "wallet": {"credits": 42},
                "active_course": "bitcoin_mastery",
            }
        },
        "agents": {
            "7": {"owner_id": uid, "name": f"user{uid}-Agent"}
        },
    }

    monkeypatch.setattr(onboarding, "OWNER_TELEGRAM_ID", "999999999")
    monkeypatch.setattr(onboarding, "user_exists", lambda user_id: str(user_id) == uid)
    monkeypatch.setattr(onboarding, "get_display_name", lambda *args: "Existing User")
    monkeypatch.setattr(onboarding, "can_start_onboarding", lambda **kwargs: True)
    monkeypatch.setattr(onboarding.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(
        onboarding,
        "_has_valid_invite",
        lambda user_id: False,
    )

    bot = FakeBot()
    onboarding.register(bot)

    start = next(
        fn for kind, meta, fn in bot.handlers
        if kind == "message" and meta.get("commands") == ["start"]
    )

    msg = types.SimpleNamespace(
        from_user=types.SimpleNamespace(id=uid),
        chat=types.SimpleNamespace(id=555),
        text="/start",
    )
    start(msg)

    assert len(bot.messages) == 1
    assert "Dashboard" in bot.messages[0]["text"]
    assert "Credits: 42" in bot.messages[0]["text"]
    assert "סוכנים שלך: 1" in bot.messages[0]["text"]
    assert "🚀 הצטרף ל-SLH" not in bot.messages[0]["text"]
