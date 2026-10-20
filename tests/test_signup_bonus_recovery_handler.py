"""Regression for /start recovery of an interrupted signup gift marker."""

import sys
import types

from handlers import onboarding_v2


class _Bot:
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


def _register_start(monkeypatch, uid, marker_result, grant_result):
    import state_manager
    from core import onboarding_rewards

    calls = []
    monkeypatch.setattr(onboarding_v2, "OWNER_TELEGRAM_ID", "999999999")
    monkeypatch.setattr(onboarding_v2, "user_exists", lambda user_id: True)
    monkeypatch.setattr(onboarding_v2, "get_display_name", lambda *args, **kwargs: "Test User")
    monkeypatch.setattr(
        onboarding_v2,
        "get_investor_snapshot",
        lambda user_id: {
            "identity": {"display_name": "Test User"},
            "wallet": {"credits": 0, "staked": 0, "live_token_balance": 0},
            "academy": {"enrolled": []},
            "tasks": {"open": 0},
        },
    )
    monkeypatch.setattr(state_manager, "load_db", lambda: {"users": {uid: {"wallet": {"credits": 0}}}, "agents": {}})
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

    bot = _Bot()
    onboarding_v2.register(bot)
    start = next(fn for meta, fn in bot.message_handlers if meta.get("commands") == ["start"])
    message = types.SimpleNamespace(
        text="/start",
        chat=types.SimpleNamespace(id=int(uid)),
        from_user=types.SimpleNamespace(id=int(uid), is_bot=False),
    )
    start(message)
    return bot, calls


def test_start_recreates_missing_marker_for_explicitly_eligible_user(monkeypatch):
    uid = "5010371391"
    bot, calls = _register_start(
        monkeypatch,
        uid,
        {"status": "PENDING"},
        {"status": "GRANTED", "credits_awarded": 5},
    )

    assert calls == [("mark", uid), ("grant", uid)]
    assert any("+5 Credits" in text for _, text, _ in bot.sent)


def test_start_does_not_retroactively_enroll_existing_user_without_eligibility(monkeypatch):
    uid = "5010371391"
    bot, calls = _register_start(
        monkeypatch,
        uid,
        {"status": "BLOCKED", "reason": "SIGNUP_BONUS_ELIGIBILITY_MISSING"},
        {"status": "NOT_PENDING"},
    )

    assert calls == [("mark", uid), ("grant", uid)]
    assert not any("מתנת ההצטרפות" in text for _, text, _ in bot.sent)
