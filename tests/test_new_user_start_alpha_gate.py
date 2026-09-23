"""Isolated regression coverage for new-user /start invite routing."""

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


def _load_onboarding(monkeypatch, db):
    import state_manager
    import core.profile_manager as profile_manager
    import core.agent_registry as agent_registry

    monkeypatch.setattr(state_manager, "load_db", lambda: db)
    monkeypatch.setattr(
        state_manager,
        "atomic_update",
        lambda fn: (fn(db), db)[1],
    )

    def exists(uid):
        return str(uid) in db["users"]

    monkeypatch.setattr(profile_manager, "user_exists", exists)
    monkeypatch.setattr(profile_manager, "update_user", lambda *a, **k: None)
    monkeypatch.setattr(agent_registry, "create_agent", lambda *a, **k: (1, {}))

    import handlers.onboarding_v2 as onboarding
    onboarding = importlib.reload(onboarding)
    monkeypatch.setattr(onboarding, "user_exists", exists)
    monkeypatch.setattr(onboarding, "get_display_name", lambda uid, user: "New User")
    monkeypatch.setattr(onboarding, "OWNER_TELEGRAM_ID", "999")
    return onboarding


def test_new_user_start_with_valid_referral_opens_alpha(monkeypatch):
    db = {
        "users": {"100": {"wallet": {"credits": 0, "staked": 0}}},
        "pending_referrals": {},
        "agents": {},
    }
    onboarding = _load_onboarding(monkeypatch, db)

    bot = FakeBot()
    onboarding.register(bot)
    start = next(
        fn for kind, meta, fn in bot.handlers
        if kind == "message" and meta.get("commands") == ["start"]
    )

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
    monkeypatch.delenv("ALPHA_INVITE_OPEN", raising=False)
    db = {"users": {"100": {"wallet": {}}}, "pending_referrals": {}, "agents": {}}
    onboarding = _load_onboarding(monkeypatch, db)

    bot = FakeBot()
    onboarding.register(bot)
    start = next(
        fn for kind, meta, fn in bot.handlers
        if kind == "message" and meta.get("commands") == ["start"]
    )
    start(Message("200", "/start"))

    assert any("נדרש Invite" in msg[1] for msg in bot.messages)


def test_owner_start_reaches_canonical_dashboard(monkeypatch):
    db = {
        "users": {"999": {"wallet": {"credits": 10, "staked": 2}, "active_course": "bitcoin_mastery"}},
        "pending_referrals": {},
        "agents": {},
    }
    onboarding = _load_onboarding(monkeypatch, db)

    bot = FakeBot()
    onboarding.register(bot)
    start = next(
        fn for kind, meta, fn in bot.handlers
        if kind == "message" and meta.get("commands") == ["start"]
    )
    start(Message("999", "/start"))

    assert len(bot.messages) == 1
    assert "המערכת מזהה אותך כבעלים" in bot.messages[0][1]
    assert "🌟 ה-Dashboard שלך" in bot.messages[0][1]
    assert bot.messages[0][2].get("reply_markup") is not None
