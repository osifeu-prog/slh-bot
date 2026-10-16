from unittest.mock import Mock

import state_manager
from core.notification_preferences import (
    get_notification_preferences,
    send_progress_update,
    set_progress_updates,
    should_send_notification,
)


def _db():
    return {"users": {"123": {}, "456": {}}}


def _install(monkeypatch, db):
    monkeypatch.setattr(state_manager, "load_db", lambda: db)
    monkeypatch.setattr(state_manager, "atomic_update", lambda mutate: mutate(db))


def test_stop_notifications_only_changes_callers_preference(monkeypatch):
    db = _db()
    _install(monkeypatch, db)

    result = set_progress_updates("123", False)

    assert result["ok"] is True
    assert db["users"]["123"]["notification_preferences"]["progress_updates_enabled"] is False
    assert "notification_preferences" not in db["users"]["456"]
    assert get_notification_preferences("123")["progress_updates_enabled"] is False


def test_opt_out_suppresses_only_allowlisted_noncritical_messages(monkeypatch):
    db = _db()
    db["users"]["123"]["notification_preferences"] = {"progress_updates_enabled": False}
    _install(monkeypatch, db)

    assert should_send_notification("123", "progress") is False
    assert should_send_notification("123", "milestone") is False
    assert should_send_notification("123", "payment") is True
    assert should_send_notification("123", "security") is True
    assert should_send_notification("123", "unknown") is True


def test_sender_does_not_send_when_opted_out_and_sends_when_enabled(monkeypatch):
    db = _db()
    db["users"]["123"]["notification_preferences"] = {"progress_updates_enabled": False}
    _install(monkeypatch, db)
    bot = Mock()

    sent = send_progress_update(bot, "123", "progress", kind="progress")
    assert sent is False
    bot.send_message.assert_not_called()

    set_progress_updates("123", True)
    sent = send_progress_update(bot, "123", "progress", kind="progress")
    assert sent is True
    bot.send_message.assert_called_once_with("123", "progress")


def test_invalid_or_missing_user_fails_without_creating_preferences(monkeypatch):
    db = _db()
    _install(monkeypatch, db)

    assert set_progress_updates("not-a-uid", False)["error"] == "INVALID_USER_ID"
    assert set_progress_updates("999", False)["error"] == "USER_NOT_FOUND"
    assert should_send_notification("999", "progress") is True
    assert db["users"]["123"] == {}
