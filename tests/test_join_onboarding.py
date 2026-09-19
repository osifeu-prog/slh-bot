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

    monkeypatch.setitem(sys.modules, "core.agent_registry", fake_agent_module)
    monkeypatch.setitem(sys.modules, "core.reward_engine", fake_reward_module)
    monkeypatch.setitem(sys.modules, "core.holiday_campaign", fake_holiday_module)
    monkeypatch.setitem(sys.modules, "core.academy_manager", fake_academy_module)

    import handlers.join_handler as join_handler
    join_handler = importlib.reload(join_handler)

    monkeypatch.setattr(join_handler, "profile_manager", profile)
    monkeypatch.setattr(join_handler, "user_exists", user_exists)
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

    assert len(agents) == 1
    assert agents[0]["owner_id"] == uid
    assert agents[0]["name"] == f"user{uid}-Agent"

    assert any(r["reason"] == "welcome_bonus" for r in rewards)
    assert ("123456790", "bitcoin_mastery") in courses
    assert "נרשמת בהצלחה" in group.replies[-1]["text"]
    assert "שיעור 1" in group.replies[-1]["text"]
