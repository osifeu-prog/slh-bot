import json

import handlers.connections_status_handler as target


def test_github_check_blocks_when_token_missing(monkeypatch):
    monkeypatch.delenv("GIT_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert target._github_check() == ("BLOCKED", "GITHUB_TOKEN_MISSING")


def test_github_check_passes_only_for_expected_repository(monkeypatch):
    monkeypatch.setenv("GIT_TOKEN", "test-token")

    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self):
            return json.dumps({"full_name": "osifeu-prog/slh-bot"}).encode()

    captured = {}
    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["authorization"] = request.get_header("Authorization")
        return Response()

    monkeypatch.setattr(target.urllib.request, "urlopen", fake_urlopen)
    assert target._github_check() == ("PASS", "REPOSITORY_READ_OK")
    assert captured["url"].endswith("/repos/osifeu-prog/slh-bot")
    assert captured["timeout"] == 10
    assert captured["authorization"] == "Bearer test-token"


def test_github_check_does_not_expose_http_error_body(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def fake_urlopen(_request, timeout):
        raise target.urllib.error.HTTPError(
            "https://api.github.com/repos/osifeu-prog/slh-bot",
            401, "Unauthorized", {}, None
        )

    monkeypatch.setattr(target.urllib.request, "urlopen", fake_urlopen)
    assert target._github_check() == ("BLOCKED", "GITHUB_HTTP_401")


def test_railway_check_reports_missing_explicit_token_without_secret(monkeypatch):
    monkeypatch.delenv("SLH_RAILWAY_TOKEN", raising=False)
    monkeypatch.setenv("SLH_RAILWAY_PROJECT_ID", "project")
    monkeypatch.setenv("SLH_RAILWAY_ENVIRONMENT_ID", "environment")
    monkeypatch.setenv("SLH_RAILWAY_SERVICE_ID", "service")
    status, reason = target._railway_check()
    assert status == "BLOCKED"
    assert reason == "SLH_RAILWAY_CREDENTIALS_MISSING"


def test_status_is_read_only_and_contains_timestamp(monkeypatch):
    monkeypatch.setattr(target, "_github_check", lambda: ("PASS", "REPOSITORY_READ_OK"))
    monkeypatch.setattr(target, "_railway_check", lambda: ("BLOCKED", "SLH_RAILWAY_CREDENTIALS_MISSING"))
    result = target.connections_status_text()
    assert "Overall: ATTENTION" in result
    assert "GitHub: PASS" in result
    assert "Railway: BLOCKED" in result
    assert "Checked at (UTC):" in result
    assert "No secrets displayed" in result
    assert "No provider settings, deployments, balances, or ledgers changed." in result
