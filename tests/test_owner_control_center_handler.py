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

def test_live_action_queue_is_shown_by_control_center_report(monkeypatch):
    import handlers.owner_control_center_handler as handler

    state = {
        "available": True,
        "overall": "DEGRADED",
        "blockers": ["system_check"],
        "warnings": ["new_user_e2e_pending"],
        "current_state": {"bnb_settlement": "CLOSED", "ton_settlement": "CLOSED"},
        "readiness": {"runtime": "DEGRADED"},
        "actions": [
            {
                "id": "collect_ci_evidence",
                "title": "איסוף ראיות CI עדכניות",
                "status": "SAFE_PROPOSAL",
                "reason": "CI evidence is not yet correlated.",
                "safe": True,
                "mutation": False,
                "owner_required": False,
            },
            {
                "id": "complete_bnb_opening_evidence",
                "title": "השלמת ראיות BNB — השער נשאר סגור עד אימות ואישור",
                "status": "OWNER_REQUIRED",
                "reason": "BNB proof remains incomplete.",
                "safe": False,
                "mutation": True,
                "owner_required": True,
            },
        ],
    }
    monkeypatch.setattr(handler, "_load_release_state", lambda: state)

    report = handler.build_report()
    rendered = handler.format_report(report)

    assert report["next_safe_step"]["id"] == "collect_ci_evidence"
    assert "תור הפעולות הנוכחי" in rendered
    assert "איסוף ראיות CI עדכניות" in rendered
    assert "נדרש אישור OWNER" in rendered
    assert "לא נשלחה עסקה" in rendered


def test_unavailable_live_action_queue_fails_closed():
    import handlers.owner_control_center_handler as handler

    report = {
        "run_id": "test",
        "timestamp_utc": "2026-10-12T00:00:00+00:00",
        "runtime": {"git_sha": "abc"},
        "checks": [],
        "release_state": {
            "available": False,
            "overall": "UNKNOWN",
            "error": "TimeoutError",
            "blockers": [],
            "warnings": [],
            "current_state": {},
            "readiness": {},
            "actions": [],
        },
        "next_safe_step": handler.next_safe_step({
            "available": False,
            "overall": "UNKNOWN",
            "error": "TimeoutError",
            "actions": [],
        }),
    }
    rendered = handler.format_report(report)

    assert "תור הפעולות לא אומת" in rendered
    assert "TimeoutError" in rendered
    assert report["next_safe_step"]["status"] == "UNKNOWN"

def test_ai_provider_degradation_appears_as_owner_action(monkeypatch):
    import handlers.owner_control_center_handler as handler

    state = {
        "available": True,
        "overall": "DEGRADED",
        "blockers": [],
        "warnings": [],
        "current_state": {"bnb_settlement": "CLOSED", "ton_settlement": "CLOSED"},
        "readiness": {"runtime": "DEGRADED"},
        "actions": [
            {
                "id": "collect_ci_evidence",
                "title": "איסוף ראיות CI עדכניות",
                "status": "SAFE_PROPOSAL",
                "reason": "Collect current CI evidence.",
                "safe": True,
                "mutation": False,
                "owner_required": False,
            }
        ],
    }
    ai = {
        "available": True,
        "status": "DEGRADED",
        "last_request_status": "DEGRADED",
        "last_provider": "",
        "reason_code": "all_providers_failed",
        "checked_at": "2026-10-12T17:00:00+00:00",
        "age_minutes": 2,
        "providers": {
            "gemini": {"status": "RATE_LIMITED", "model": "gemini-2.5-flash", "reason_code": "quota_or_rate_limit"},
            "groq": {"status": "RATE_LIMITED", "model": "openai/gpt-oss-20b", "reason_code": "quota_or_rate_limit"},
        },
    }
    monkeypatch.setattr(handler, "_load_release_state", lambda: state)
    monkeypatch.setattr(handler, "_load_ai_health", lambda now=None: ai)

    report = handler.build_report()
    rendered = handler.format_report(report)

    assert report["next_safe_step"]["id"] == "restore_ai_provider_availability"
    assert "AI provider health" in rendered
    assert "AI: DEGRADED" in rendered
    assert "שחזור זמינות ספקי AI" in rendered
    assert "אל תשתף מפתחות" in rendered


def test_ai_health_stale_status_is_not_promoted_to_active_issue(monkeypatch):
    import handlers.owner_control_center_handler as handler

    state = {
        "available": True,
        "overall": "GREEN",
        "blockers": [],
        "warnings": [],
        "current_state": {},
        "readiness": {},
        "actions": [],
    }
    ai = {
        "available": True,
        "status": "STALE",
        "last_request_status": "DEGRADED",
        "last_provider": "",
        "reason_code": "all_providers_failed",
        "checked_at": "2026-10-12T10:00:00+00:00",
        "age_minutes": 600,
        "providers": {},
    }
    monkeypatch.setattr(handler, "_load_release_state", lambda: state)
    monkeypatch.setattr(handler, "_load_ai_health", lambda now=None: ai)

    report = handler.build_report()
    rendered = handler.format_report(report)

    assert report["next_safe_step"]["id"] == "manual_review" or report["next_safe_step"]["id"] == "none"
    assert "AI: STALE" in rendered
    assert not any(
        item.get("id") == "restore_ai_provider_availability"
        for item in report["release_state"]["actions"]
    )

