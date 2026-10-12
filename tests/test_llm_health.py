from pathlib import Path

from core.llm_health import classify_provider_result, load_health, record_provider_result, record_request_result


def test_rate_limit_is_classified_without_retaining_raw_provider_error(tmp_path):
    path = tmp_path / "state" / "ai_health.json"
    status, reason = classify_provider_result(
        "gemini", 'Gemini Error: {"code":429,"message":"quota reached secret=NEVER_STORE"}'
    )
    assert (status, reason) == ("RATE_LIMITED", "quota_or_rate_limit")
    record_provider_result("gemini", status, model="gemini-2.5-flash", reason_code=reason, path=path)
    record_request_result("DEGRADED", reason_code="all_providers_failed", path=path)

    raw = path.read_text(encoding="utf-8")
    health = load_health(path=path)
    assert "NEVER_STORE" not in raw
    assert "quota reached" not in raw
    assert health["providers"]["gemini"]["status"] == "RATE_LIMITED"
    assert health["last_request"]["status"] == "DEGRADED"


def test_non_rate_limit_error_is_sanitized_and_unknown_providers_ignored(tmp_path):
    path = tmp_path / "state" / "ai_health.json"
    status, reason = classify_provider_result("groq", "LLM Error: authorization failed api_key=DO_NOT_STORE")
    assert (status, reason) == ("UNAVAILABLE", "provider_error")
    record_provider_result("groq", status, reason_code=reason, path=path)
    record_provider_result("unknown", "HEALTHY", model="test", path=path)
    health = load_health(path=path)
    assert set(health["providers"]) == {"groq"}
    assert health["providers"]["groq"]["status"] == "UNAVAILABLE"
    assert "DO_NOT_STORE" not in path.read_text(encoding="utf-8")
