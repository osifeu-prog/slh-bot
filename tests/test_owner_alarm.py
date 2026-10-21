import json
from datetime import datetime
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
