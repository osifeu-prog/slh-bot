import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from handlers import alarm_handler as alarm


def test_next_fire_time_uses_jerusalem_and_rolls_to_next_day():
    tz = ZoneInfo("Asia/Jerusalem")
    now = datetime(2026, 10, 21, 20, 0, tzinfo=tz)
    assert alarm.next_fire_time("07:00", now).strftime("%Y-%m-%d %H:%M") == "2026-10-22 07:00"


def test_next_fire_time_rolls_forward_if_time_passed():
    tz = ZoneInfo("Asia/Jerusalem")
    now = datetime(2026, 10, 21, 8, 0, tzinfo=tz)
    assert alarm.next_fire_time("07:00", now).strftime("%Y-%m-%d %H:%M") == "2026-10-22 07:00"


def test_next_fire_time_rejects_invalid_values():
    for value in ("25:00", "12:60", "bad", "7"):
        try:
            alarm.next_fire_time(value, datetime(2026, 10, 21, 8, 0, tzinfo=ZoneInfo("Asia/Jerusalem")))
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted invalid time: {value}")


def test_schedule_and_disable_are_persistent(tmp_path, monkeypatch):
    target = tmp_path / "alarm.json"
    monkeypatch.setenv("SLH_ALARM_STATE_FILE", str(target))
    now = datetime(2026, 10, 21, 20, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
    data = alarm.schedule_alarm(12345, "07:00", now=now)
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["enabled"] is True
    assert saved["chat_id"] == 12345
    assert saved["local_time"] == "2026-10-22 07:00"
    assert data["timezone"] == "Asia/Jerusalem"
    alarm.disable_alarm()
    assert json.loads(target.read_text(encoding="utf-8"))["enabled"] is False



class _FakeAlarmBot:
    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []

    def send_message(self, chat_id, message):
        self.sent.append((chat_id, message))
        if self.fail:
            raise RuntimeError("telegram unavailable")


def _due_alarm(now, bot_key="test-bot"):
    return {
        "enabled": True,
        "chat_id": 12345,
        "bot_key": bot_key,
        "fire_at": (now - timedelta(seconds=1)).isoformat(),
        "attempts": 0,
    }


def test_due_alarm_send_failure_keeps_alarm_enabled_and_schedules_retry(tmp_path, monkeypatch):
    target = tmp_path / "alarm.json"
    monkeypatch.setenv("SLH_ALARM_STATE_FILE", str(target))
    now = datetime(2026, 10, 21, 8, 0, tzinfo=timezone.utc)
    bot = _FakeAlarmBot(fail=True)
    monkeypatch.setattr(alarm, "_SCHEDULER_BOTS", {"test-bot": bot})
    monkeypatch.setattr(alarm, "_morning_message", lambda: "test alarm")
    alarm.save_state(_due_alarm(now))

    assert alarm._deliver_due_alarm(now=now) == "send_failed"
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["enabled"] is True
    assert saved["attempts"] == 1
    assert saved["last_error"] == "RuntimeError"
    assert datetime.fromisoformat(saved["next_attempt_at"]) > now
    assert bot.sent == [(12345, "test alarm")]


def test_due_alarm_success_sends_and_completes_one_shot(tmp_path, monkeypatch):
    target = tmp_path / "alarm.json"
    monkeypatch.setenv("SLH_ALARM_STATE_FILE", str(target))
    now = datetime(2026, 10, 21, 8, 0, tzinfo=timezone.utc)
    bot = _FakeAlarmBot()
    monkeypatch.setattr(alarm, "_SCHEDULER_BOTS", {"test-bot": bot})
    monkeypatch.setattr(alarm, "_morning_message", lambda: "test alarm")
    alarm.save_state(_due_alarm(now))

    assert alarm._deliver_due_alarm(now=now) == "sent"
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["enabled"] is False
    assert saved["fired_at"] == now.isoformat()
    assert "next_attempt_at" not in saved
    assert bot.sent == [(12345, "test alarm")]


def test_start_scheduler_migrates_legacy_pending_alarm(tmp_path, monkeypatch):
    target = tmp_path / "alarm.json"
    monkeypatch.setenv("SLH_ALARM_STATE_FILE", str(target))
    now = datetime(2026, 10, 21, 8, 0, tzinfo=timezone.utc)
    legacy = _due_alarm(now)
    legacy.pop("bot_key")
    alarm.save_state(legacy)

    bot = _FakeAlarmBot()
    monkeypatch.setattr(alarm.threading.Thread, "start", lambda self: None)
    monkeypatch.setattr(alarm, "_SCHEDULER_STARTED", False)
    monkeypatch.setattr(alarm, "_SCHEDULER_BOTS", {})
    alarm.start_scheduler(bot)

    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["enabled"] is True
    assert saved["bot_key"] == alarm._bot_key(bot)


def test_bot_key_is_stable_when_token_secret_rotates():
    class _TokenBot:
        def __init__(self, token):
            self.token = token

    first = _TokenBot("123456:old-secret")
    rotated = _TokenBot("123456:new-secret")
    other_bot = _TokenBot("987654:other-secret")

    assert alarm._bot_key(first) == alarm._bot_key(rotated)
    assert alarm._bot_key(first) != alarm._bot_key(other_bot)
