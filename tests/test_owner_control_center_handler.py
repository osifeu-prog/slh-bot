import json

from handlers.owner_control_center_handler import (
    CALLBACK_TTL_SECONDS,
    _git_sha,
    callback_data,
    format_report,
    next_safe_step,
    parse_callback,
    save_report,
    load_last_report,
    register,
)


def test_callback_payload_is_valid_and_expires():
    assert parse_callback(callback_data("audit", issued_at=1000), now=1001) == "audit"
    assert parse_callback(callback_data("audit", issued_at=1000), now=1000 + CALLBACK_TTL_SECONDS + 1) is None
    assert parse_callback("slhcc:audit:not-a-time", now=1001) is None
    assert parse_callback("slhcc:unknown:1000", now=1001) is None
    assert parse_callback("slhcc:audit:2000", now=1000) is None


def test_next_safe_step_is_selection_only():
    step = next_safe_step()
    assert step["id"] == "verify_runtime_sha"
    assert step["status"] == "UNKNOWN"
    assert "Railway" in step["reason"]
    assert "viewer אינה זמינה" not in step["reason"]


def test_git_sha_prefers_railway_injected_commit(monkeypatch):
    expected = "9adb0ed89ebe2ab16019e290e64ffe564bfca995"
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", expected)
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    monkeypatch.delenv("SOURCE_VERSION", raising=False)
    assert _git_sha() == expected


def test_git_sha_rejects_invalid_environment_value(monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "unknown")
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    monkeypatch.delenv("SOURCE_VERSION", raising=False)
    assert _git_sha() != "unknown"


def test_report_persistence_and_format(tmp_path):
    report = {
        "run_id": "test123",
        "timestamp_utc": "2026-10-12T00:00:00+00:00",
        "runtime": {"git_sha": "abc123"},
        "checks": [{"name": "sample", "status": "UNKNOWN", "evidence": "not verified"}],
        "next_safe_step": {"title": "verify runtime"},
    }
    path = tmp_path / "nested" / "last_report.json"
    save_report(report, path=path)
    assert json.loads(path.read_text(encoding="utf-8")) == report
    assert load_last_report(path=path) == report
    text = format_report(report)
    assert "READ ONLY" in text
    assert "UNKNOWN" in text
    assert "לא נשלחה עסקה" in text


def test_missing_report_returns_none(tmp_path):
    assert load_last_report(path=tmp_path / "missing.json") is None


def test_owner_control_center_does_not_claim_existing_control_command():
    class RecordingBot:
        def __init__(self):
            self.message_commands = []

        def message_handler(self, commands=None, **_kwargs):
            def decorator(fn):
                self.message_commands.extend(commands or [])
                return fn
            return decorator

        def callback_query_handler(self, func=None, **_kwargs):
            def decorator(fn):
                return fn
            return decorator

    bot = RecordingBot()
    register(bot)

    assert "control_center" in bot.message_commands
    assert "control" not in bot.message_commands
