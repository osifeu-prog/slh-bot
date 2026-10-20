"""Isolated E2E regression test for the new-user /join onboarding flow.

The test never touches production state.db.json or Telegram.
"""

import importlib
import sys
import types


class FakeBot:
    def __init__(self):
        self.handlers = []

    def message_handler(self, **kwargs):
        def decorator(fn):
            self.handlers.append((kwargs, fn))
            return fn
        return decorator

    def reply_to(self, msg, text, **kwargs):
        msg.replies.append({"text": text, **kwargs})


class FakeMessage:
    def __init__(self, uid, text):
        self.from_user = types.SimpleNamespace(id=uid)
        self.text = text
        self.replies = []


def test_new_user_join_completes_agent_profile_and_academy_flow(monkeypatch):
    uid = "123456790"
    db = {"users": {}, "pending_referrals": {}}
    agents = []
    rewards = []
    courses = []
    signup_rewards = []

    profile = types.SimpleNamespace(
        update_user=lambda user_id, data: (
            db["users"].setdefault(str(user_id), {}).update(data)
        )
    )

    def user_exists(user_id):
        return str(user_id) in db["users"]

    def create_agent(name, owner_id=None, **kwargs):
        agents.append({"name": name, "owner_id": str(owner_id), **kwargs})
        return {"name": name, "owner_id": str(owner_id)}

    def grant(user_id, reason, **kwargs):
        rewards.append({"uid": str(user_id), "reason": reason, **kwargs})
        return True

    def start_course(user_id, course_id):
        courses.append((str(user_id), course_id))
        return True

    monkeypatch.setattr(
        sys.modules["core.profile_manager"],
        "update_user",
        profile.update_user,
        raising=False,
    )
    monkeypatch.setattr(
        sys.modules["core.profile_manager"],
        "user_exists",
        user_exists,
        raising=False,
    )

    fake_agent_module = types.SimpleNamespace(create_agent=create_agent)
    fake_reward_module = types.SimpleNamespace(grant=grant)
    fake_holiday_module = types.SimpleNamespace(
        record_entry=lambda *args, **kwargs: True,
        finalize_entry=lambda *args, **kwargs: True,
        settle=lambda *args, **kwargs: True,
    )
    fake_academy_module = types.SimpleNamespace(start_course=start_course)
    fake_signup_module = types.SimpleNamespace(
        mark_signup_bonus_pending=lambda user_id: signup_rewards.append(("mark", str(user_id))) or {"status": "PENDING"},
        grant_signup_bonus=lambda user_id: signup_rewards.append(("grant", str(user_id))) or {"status": "GRANTED", "credits_awarded": 5},
    )

    monkeypatch.setitem(sys.modules, "core.agent_registry", fake_agent_module)
    monkeypatch.setitem(sys.modules, "core.reward_engine", fake_reward_module)
    monkeypatch.setitem(sys.modules, "core.holiday_campaign", fake_holiday_module)
    monkeypatch.setitem(sys.modules, "core.academy_manager", fake_academy_module)
    monkeypatch.setitem(sys.modules, "core.onboarding_rewards", fake_signup_module)

    import handlers.join_handler as join_handler
    join_handler = importlib.reload(join_handler)

    monkeypatch.setattr(join_handler, "profile_manager", profile)
    monkeypatch.setattr(join_handler, "user_exists", user_exists)
    monkeypatch.setattr(join_handler.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(join_handler, "can_start_onboarding", lambda **kwargs: True)
    monkeypatch.setattr(join_handler, "OWNER_TELEGRAM_ID", "999999999")

    bot = FakeBot()
    join_handler.register(bot)

    command_handler = next(
        fn for meta, fn in bot.handlers
        if meta.get("commands") == ["join"]
    )
    text_handler = next(
        fn for meta, fn in bot.handlers
        if "func" in meta
    )

    start = FakeMessage(uid, "/join")
    command_handler(start)
    assert start.replies[-1]["text"] == "👋 ברוך הבא! איך קוראים לך? (שם מלא)"
    assert join_handler.user_states[uid]["step"] == "name"

    name = FakeMessage(uid, "Test Alpha User")
    text_handler(name)
    assert join_handler.user_states[uid]["step"] == "group"
    assert "Test Alpha User" in name.replies[-1]["text"]

    group = FakeMessage(uid, "Bitcoin Masters")
    text_handler(group)

    assert uid not in join_handler.user_states
    assert db["users"][uid]["joined"] is True
    assert db["users"][uid]["role"] == "student"
    assert db["users"][uid]["name"] == "Test Alpha User"
    assert db["users"][uid]["group"] == "Bitcoin Masters"
    assert db["users"][uid]["onboarding_signup_bonus_eligible_at"]

    assert len(agents) == 1
    assert agents[0]["owner_id"] == uid
    assert agents[0]["name"] == f"user{uid}-Agent"

    assert any(r["reason"] == "welcome_bonus" for r in rewards)
    assert ("123456790", "bitcoin_mastery") in courses
    assert signup_rewards == [("mark", uid), ("grant", uid)]
    assert "מתנת הצטרפות: 5 Credits" in group.replies[-1]["text"]
    assert "נרשמת בהצלחה" in group.replies[-1]["text"]
    assert "שיעור 1" in group.replies[-1]["text"]


class _StartBot:
    def __init__(self):
        self.message_handlers = []
        self.callback_handlers = []
        self.sent = []

    def message_handler(self, **kwargs):
        def decorator(fn):
            self.message_handlers.append((kwargs, fn))
            return fn
        return decorator

    def callback_query_handler(self, **kwargs):
        def decorator(fn):
            self.callback_handlers.append((kwargs, fn))
            return fn
        return decorator

    def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))

    def answer_callback_query(self, *args, **kwargs):
        return None


def _run_existing_start_recovery(monkeypatch, uid, marker_result, grant_result):
    import state_manager
    from core import onboarding_rewards
    import handlers.onboarding_v2 as onboarding

    calls = []
    monkeypatch.setattr(onboarding, "OWNER_TELEGRAM_ID", "999999999")
    monkeypatch.setattr(onboarding, "user_exists", lambda user_id: True)
    monkeypatch.setattr(onboarding, "get_display_name", lambda *args, **kwargs: "Test User")
    monkeypatch.setattr(
        onboarding,
        "get_investor_snapshot",
        lambda user_id: {
            "identity": {"display_name": "Test User"},
            "wallet": {"credits": 0, "staked": 0, "live_token_balance": 0},
            "academy": {"enrolled": []},
            "tasks": {"open": 0},
        },
    )
    monkeypatch.setattr(
        state_manager,
        "load_db",
        lambda: {"users": {uid: {"wallet": {"credits": 0}}}, "agents": {}},
    )
    monkeypatch.setitem(
        sys.modules,
        "core.holiday_campaign",
        types.SimpleNamespace(record_entry=lambda *args, **kwargs: True),
    )

    def mark(user_id):
        calls.append(("mark", str(user_id)))
        return marker_result

    def grant(user_id):
        calls.append(("grant", str(user_id)))
        return grant_result

    monkeypatch.setattr(onboarding_rewards, "mark_signup_bonus_pending", mark)
    monkeypatch.setattr(onboarding_rewards, "grant_signup_bonus", grant)

    bot = _StartBot()
    onboarding.register(bot)
    handler = next(
        fn for meta, fn in bot.message_handlers if meta.get("commands") == ["start"]
    )
    message = types.SimpleNamespace(
        text="/start",
        chat=types.SimpleNamespace(id=int(uid)),
        from_user=types.SimpleNamespace(id=int(uid), is_bot=False),
    )
    handler(message)
    return bot, calls


def test_start_recovers_interrupted_signup_gift_for_durably_eligible_user(monkeypatch):
    uid = "5010371391"
    bot, calls = _run_existing_start_recovery(
        monkeypatch,
        uid,
        {"status": "PENDING"},
        {"status": "GRANTED", "credits_awarded": 5},
    )

    assert calls == [("mark", uid), ("grant", uid)]
    assert any("+5 Credits" in text for _, text, _ in bot.sent)


def test_start_never_enrolls_existing_user_without_signup_eligibility(monkeypatch):
    uid = "5010371391"
    bot, calls = _run_existing_start_recovery(
        monkeypatch,
        uid,
        {"status": "BLOCKED", "reason": "SIGNUP_BONUS_ELIGIBILITY_MISSING"},
        {"status": "NOT_PENDING"},
    )

    assert calls == [("mark", uid), ("grant", uid)]
    assert not any("מתנת ההצטרפות" in text for _, text, _ in bot.sent)
