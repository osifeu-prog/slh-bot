"""Isolated regression coverage for new-user /start invite routing."""

import importlib
import sys
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
        self.messages.append((chat_id, text, kwargs))

    def answer_callback_query(self, call_id, text=None):
        self.messages.append(("callback", call_id, text))

    def get_me(self):
        return types.SimpleNamespace(username="TestAlphaBot")


class User:
    def __init__(self, uid):
        self.id = uid
        self.first_name = "New"


class Message:
    def __init__(self, uid, text):
        self.from_user = User(uid)
        self.chat = types.SimpleNamespace(id=uid)
        self.text = text


class Call:
    def __init__(self, uid, data):
        self.id = "call-1"
        self.from_user = User(uid)
        self.message = types.SimpleNamespace(chat=types.SimpleNamespace(id=uid))
        self.data = data


def test_new_user_start_with_valid_referral_opens_alpha(monkeypatch):
    import state_manager

    db = {
        "users": {"100": {"wallet": {"credits": 0, "staked": 0}}},
        "pending_referrals": {},
        "agents": {},
    }

    monkeypatch.setattr(state_manager, "load_db", lambda: db)
    monkeypatch.setattr(
        state_manager,
        "atomic_update",
        lambda fn: (fn(db), db)[1],
    )

    def exists(uid):
        return str(uid) in db["users"]

    fake_profile = types.SimpleNamespace(
        user_exists=exists,
        update_user=lambda *args, **kwargs: None,
    )
    fake_identity = types.SimpleNamespace(OWNER_TELEGRAM_ID="999")
    fake_agent = types.SimpleNamespace(create_agent=lambda *args, **kwargs: (1, {}))

    monkeypatch.setitem(sys.modules, "core.profile_manager", fake_profile)
    monkeypatch.setitem(sys.modules, "core.identity", fake_identity)
    monkeypatch.setitem(sys.modules, "core.agent_registry", fake_agent)

    import handlers.onboarding_v2 as onboarding
    onboarding = importlib.reload(onboarding)

    monkeypatch.setattr(onboarding, "user_exists", exists)
    monkeypatch.setattr(onboarding, "get_display_name", lambda uid, user: "New User")
    monkeypatch.setattr(onboarding, "OWNER_TELEGRAM_ID", "999")
    monkeypatch.setattr(onboarding, "record_entry", lambda *a, **k: True, raising=False)

    bot = FakeBot()
    onboarding.register(bot)

    start = next(
        fn for kind, meta, fn in bot.handlers
        if kind == "message" and meta.get("commands") == ["start"]
    )

    # Referrer 100 exists, so this invite is valid and the new user may enter Alpha.
    start(Message("200", "/start ref_100"))

    assert db["pending_referrals"]["200"] == "100"
    assert any("הצטרף למסלול ה-Alpha" in msg[1] for msg in bot.messages)

    join_cb = next(
        fn for kind, meta, fn in bot.handlers
        if kind == "callback" and meta.get("func")(Call("200", "start_join"))
    )
    join_cb(Call("200", "start_join"))

    assert any("איך קוראים לך" in msg[1] for msg in bot.messages)


def test_new_user_start_without_invite_stays_closed(monkeypatch):
    import state_manager

    db = {"users": {"100": {"wallet": {}}}, "pending_referrals": {}, "agents": {}}
    monkeypatch.setattr(state_manager, "load_db", lambda: db)

    def exists(uid):
        return str(uid) in db["users"]

    fake_profile = types.SimpleNamespace(user_exists=exists)
    monkeypatch.setitem(sys.modules, "core.profile_manager", fake_profile)
    monkeypatch.setitem(sys.modules, "core.identity", types.SimpleNamespace(OWNER_TELEGRAM_ID="999"))
    monkeypatch.setitem(sys.modules, "core.agent_registry", types.SimpleNamespace(create_agent=lambda *a, **k: (1, {})))

    import handlers.onboarding_v2 as onboarding
    onboarding = importlib.reload(onboarding)
    monkeypatch.setattr(onboarding, "user_exists", exists)
    monkeypatch.setattr(onboarding, "get_display_name", lambda uid, user: "New User")
    monkeypatch.setattr(onboarding, "OWNER_TELEGRAM_ID", "999")

    bot = FakeBot()
    onboarding.register(bot)
    start = next(
        fn for kind, meta, fn in bot.handlers
        if kind == "message" and meta.get("commands") == ["start"]
    )
    start(Message("200", "/start"))

    assert any("נדרש Invite" in msg[1] for msg in bot.messages)
