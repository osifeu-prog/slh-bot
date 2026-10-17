"""Railway deployment helper tests for scoped project-token handling."""
import pytest

from handlers import deploy_handler as target


class FakeResponse:
    def __init__(self, data):
        self._data = data
    def raise_for_status(self):
        return None
    def json(self):
        return self._data


def test_graphql_uses_project_access_token_for_project_token(monkeypatch):
    captured = {}
    def fake_post(url, *, json, headers, timeout):
        captured.update(url=url, json=json, headers=headers, timeout=timeout)
        return FakeResponse({"data": {"ok": True}})
    monkeypatch.setattr(target.requests, "post", fake_post)

    result = target._graphql("project-secret", "query { ok }", {}, token_type="project")

    assert result == {"ok": True}
    assert captured["url"] == "https://backboard.railway.com/graphql/v2"
    assert captured["headers"]["Project-Access-Token"] == "project-secret"
    assert "Authorization" not in captured["headers"]


def test_graphql_keeps_bearer_for_account_token(monkeypatch):
    captured = {}
    def fake_post(url, *, json, headers, timeout):
        captured["headers"] = headers
        return FakeResponse({"data": {"ok": True}})
    monkeypatch.setattr(target.requests, "post", fake_post)

    target._graphql("account-secret", "query { ok }", {})

    assert captured["headers"]["Authorization"] == "Bearer account-secret"
    assert "Project-Access-Token" not in captured["headers"]


def test_standard_railway_token_only_works_for_matching_target_scope(monkeypatch):
    for key in ("RAILWAY_API_TOKEN", "RAILWAY_API_TOKEN_SLH", "SLH_RAILWAY_TOKEN",
                "RAILWAY_PROJECT_TOKEN", "RAILWAY_PROJECT_TOKEN_SLH"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("RAILWAY_TOKEN", "project-token-secret")
    seen = []
    def fake_graphql(token, query, variables, *, token_type="account"):
        seen.append((token, query, token_type))
        assert token == "project-token-secret"
        assert token_type == "project"
        return {"projectToken": {"projectId": "p1", "environmentId": "e1"}}
    monkeypatch.setattr(target, "_graphql", fake_graphql)

    token, token_type = target._credentials_for_target({
        "railway_project_id": "p1",
        "railway_environment_id": "e1",
    })

    assert token == "project-token-secret"
    assert token_type == "project"
    assert len(seen) == 1
    assert "mutation" not in seen[0][1].lower()


def test_standard_railway_token_wrong_scope_fails_closed(monkeypatch):
    for key in ("RAILWAY_API_TOKEN", "RAILWAY_API_TOKEN_SLH", "SLH_RAILWAY_TOKEN",
                "RAILWAY_PROJECT_TOKEN", "RAILWAY_PROJECT_TOKEN_SLH"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("RAILWAY_TOKEN", "project-token-secret")
    monkeypatch.setattr(
        target, "_graphql",
        lambda token, query, variables, *, token_type="account": {
            "projectToken": {"projectId": "other", "environmentId": "other-env"}
        },
    )

    with pytest.raises(RuntimeError, match="RAILWAY_PROJECT_TOKEN_SCOPE_MISMATCH"):
        target._credentials_for_target({
            "railway_project_id": "p1",
            "railway_environment_id": "e1",
        })


def test_account_token_remains_available_for_cross_project_targets(monkeypatch):
    monkeypatch.setenv("RAILWAY_API_TOKEN", "account-secret")
    for key in ("RAILWAY_API_TOKEN_SLH", "SLH_RAILWAY_TOKEN", "RAILWAY_PROJECT_TOKEN",
                "RAILWAY_PROJECT_TOKEN_SLH", "RAILWAY_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        target, "_project_token_scope",
        lambda _token: (_ for _ in ()).throw(AssertionError("no project candidate should run")),
    )

    assert target._credentials_for_target({
        "railway_project_id": "p1",
        "railway_environment_id": "e1",
    }) == ("account-secret", "account")


def test_matching_project_token_is_preferred_over_account_token(monkeypatch):
    monkeypatch.setenv("RAILWAY_API_TOKEN", "account-secret")
    for key in ("RAILWAY_API_TOKEN_SLH", "SLH_RAILWAY_TOKEN", "RAILWAY_PROJECT_TOKEN",
                "RAILWAY_PROJECT_TOKEN_SLH"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("RAILWAY_TOKEN", "project-secret")
    monkeypatch.setattr(target, "_project_token_scope", lambda _token: ("p1", "e1"))

    assert target._credentials_for_target({
        "railway_project_id": "p1",
        "railway_environment_id": "e1",
    }) == ("project-secret", "project")
