import json

import pytest

import handlers.railway_control_handler as target


def test_replace_treasury_preserves_all_other_config_fields():
    original = {
        "network": "bsc",
        "rpc": "https://bsc-dataseed.binance.org/",
        "chain_id": 56,
        "symbol": "BNB",
        "token_contract": "0xACb0A09414CEA1C879c67bB7A877E4e19480f022",
        "confirmations": 15,
        "treasury_wallet": "0x468328B2a7C9b5629e87844Bb4531e7409400b34",
    }
    target_address = "0x03bf3BfB8752203353645321869FE1e90C7C300F"
    updated_raw, previous = target._updated_config(json.dumps(original), target_address)
    updated = json.loads(updated_raw)
    assert previous == original["treasury_wallet"]
    assert updated["treasury_wallet"] == target_address
    for key in original:
        if key != "treasury_wallet":
            assert updated[key] == original[key]


def test_replace_treasury_rejects_invalid_json_and_target():
    with pytest.raises(ValueError, match="SLH_BSC_CONFIG_INVALID_JSON"):
        target._updated_config("{", "0x" + "1" * 40)
    with pytest.raises(ValueError, match="TREASURY_TARGET_INVALID"):
        target._updated_config('{"treasury_wallet":"0x' + "0" * 40 + '"}', "not-address")


def test_missing_project_token_is_blocked(monkeypatch):
    monkeypatch.delenv("SLH_RAILWAY_TOKEN", raising=False)
    monkeypatch.setenv("SLH_RAILWAY_PROJECT_ID", "project")
    monkeypatch.setenv("SLH_RAILWAY_ENVIRONMENT_ID", "environment")
    monkeypatch.setenv("SLH_RAILWAY_SERVICE_ID", "service")
    with pytest.raises(RuntimeError, match="RAILWAY_CREDENTIALS_MISSING"):
        target._ids()


def test_status_does_not_print_secrets_when_token_missing(monkeypatch):
    monkeypatch.delenv("SLH_RAILWAY_TOKEN", raising=False)
    monkeypatch.setenv("SLH_RAILWAY_PROJECT_ID", "project")
    monkeypatch.setenv("SLH_RAILWAY_ENVIRONMENT_ID", "environment")
    monkeypatch.setenv("SLH_RAILWAY_SERVICE_ID", "service")
    result = target.railway_status_reply()
    assert "RAILWAY_CREDENTIALS_MISSING" in result
    assert "Bearer " not in result
    assert "token_contract" not in result


def test_ids_prefer_slh_prefixed_config_over_railway_runtime_names(monkeypatch):
    monkeypatch.setenv("SLH_RAILWAY_TOKEN", "project-scoped-token")
    monkeypatch.setenv("SLH_RAILWAY_PROJECT_ID", "slh-project")
    monkeypatch.setenv("SLH_RAILWAY_ENVIRONMENT_ID", "slh-production")
    monkeypatch.setenv("SLH_RAILWAY_SERVICE_ID", "slh-bot-service")
    # Railway's own injected identifiers must not override the explicit SLH scope.
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "railway-injected-project")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "railway-injected-environment")
    monkeypatch.setenv("RAILWAY_SERVICE_ID", "railway-injected-service")

    ctx = target._ids()

    assert ctx == {
        "token": "project-scoped-token",
        "project_id": "slh-project",
        "environment_id": "slh-production",
        "service_id": "slh-bot-service",
    }


def test_graphql_uses_project_access_token_header(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self):
            return b'{"data": {"ok": true}}'

    def fake_urlopen(request, timeout):
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(target.urllib.request, "urlopen", fake_urlopen)
    ctx = {"token": "test-token", "project_id": "p", "environment_id": "e", "service_id": "s"}
    assert target._graphql(ctx, "query { ok }") == {"ok": True}
    headers = {key.lower(): value for key, value in captured["headers"].items()}
    assert headers.get("project-access-token") == "test-token"
    assert "authorization" not in headers


def test_variable_update_requests_one_explicit_redeploy(monkeypatch):
    calls = []
    ctx = {
        "token": "scoped-token",
        "project_id": "project",
        "environment_id": "environment",
        "service_id": "service",
    }

    def fake_graphql(_ctx, query, variables=None):
        calls.append((query, variables))
        if "variableCollectionUpsert" in query:
            return {"variableCollectionUpsert": True}
        if "serviceInstanceRedeploy" in query:
            return {"serviceInstanceRedeploy": True}
        raise AssertionError("unexpected mutation")

    monkeypatch.setattr(target, "_graphql", fake_graphql)
    result = target._update_and_redeploy(ctx, "target-config")
    assert result == "DEPLOY_TRIGGERED"
    assert len(calls) == 2
    assert calls[0][1]["input"]["skipDeploys"] is True
    assert calls[0][1]["input"]["variables"] == {"SLH_BSC_CONFIG": "target-config"}
    assert "serviceInstanceRedeploy" in calls[1][0]


def test_connections_status_is_read_only_and_redacts_tokens(monkeypatch):
    for key in (
        "GIT_TOKEN", "GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN_SLH",
        "RAILWAY_API_TOKEN", "RAILWAY_API_TOKEN_SLH",
        "RAILWAY_PROJECT_TOKEN", "RAILWAY_PROJECT_TOKEN_SLH", "RAILWAY_TOKEN",
        "SLH_RAILWAY_TOKEN", "SLH_RAILWAY_PROJECT_ID",
        "SLH_RAILWAY_ENVIRONMENT_ID", "SLH_RAILWAY_SERVICE_ID",
    ):
        monkeypatch.delenv(key, raising=False)

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"full_name":"osifeu-prog/slh-bot"}'

    captured = {}

    def fake_urlopen(request, timeout):
        captured["method"] = request.get_method()
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(target.urllib.request, "urlopen", fake_urlopen)
    result = target.connections_status_reply()

    assert captured["method"] == "GET"
    assert captured["url"] == "https://api.github.com/repos/osifeu-prog/slh-bot"
    assert captured["timeout"] == 8
    assert "GitHub API read: PASS" in result
    assert "GitHub write credential (/git commit): MISSING" in result
    assert "Railway account/workspace token (cross-project targets): MISSING" in result
    assert "Railway project token candidate (single project/environment): MISSING" in result
    assert "SLH scoped Railway integration: BLOCKED" in result
    assert "No secrets printed" in result
    assert "Bearer " not in result


def test_connections_status_validates_railway_scope_without_mutations(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "github-secret-value")
    monkeypatch.setenv("GIT_TOKEN", "git-secret-value")
    monkeypatch.setenv("SLH_RAILWAY_TOKEN", "railway-secret-value")
    monkeypatch.setenv("SLH_RAILWAY_PROJECT_ID", "project-1")
    monkeypatch.setenv("SLH_RAILWAY_ENVIRONMENT_ID", "environment-1")
    monkeypatch.setenv("SLH_RAILWAY_SERVICE_ID", "service-1")
    monkeypatch.delenv("RAILWAY_API_TOKEN", raising=False)

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"full_name":"osifeu-prog/slh-bot"}'

    captured = []

    def fake_urlopen(request, timeout):
        captured.append(("github", request.get_method(), request.full_url))
        return Response()

    def fake_graphql(ctx, query, variables=None):
        captured.append(("railway", query))
        assert ctx["token"] == "railway-secret-value"
        assert "query" in query.lower()
        assert "mutation" not in query.lower()
        return {
            "projectToken": {
                "projectId": "project-1",
                "environmentId": "environment-1",
            }
        }

    monkeypatch.setattr(target.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(target, "_graphql", fake_graphql)
    result = target.connections_status_reply()

    assert "GitHub API read: PASS" in result
    assert "GitHub write credential (/git commit): CONFIGURED" in result
    assert "SLH scoped Railway integration: PASS" in result
    assert "github-secret-value" not in result
    assert "git-secret-value" not in result
    assert "railway-secret-value" not in result
    assert "variableCollectionUpsert" not in repr(captured)
    assert "serviceInstanceRedeploy" not in repr(captured)


def test_connections_status_validates_standard_railway_token_scope(monkeypatch):
    for key in (
        "SLH_RAILWAY_TOKEN", "RAILWAY_PROJECT_TOKEN", "RAILWAY_PROJECT_TOKEN_SLH",
        "RAILWAY_API_TOKEN", "RAILWAY_API_TOKEN_SLH",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("RAILWAY_TOKEN", "project-token-secret")
    monkeypatch.setenv("SLH_RAILWAY_PROJECT_ID", "project-1")
    monkeypatch.setenv("SLH_RAILWAY_ENVIRONMENT_ID", "environment-1")
    monkeypatch.setenv("SLH_RAILWAY_SERVICE_ID", "service-1")

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self):
            return b'{"full_name":"osifeu-prog/slh-bot"}'

    monkeypatch.setattr(
        target.urllib.request, "urlopen",
        lambda request, timeout: Response(),
    )
    calls = []

    def fake_graphql(ctx, query, variables=None):
        calls.append(query)
        assert ctx["token"] == "project-token-secret"
        assert "mutation" not in query.lower()
        return {
            "projectToken": {
                "projectId": "project-1",
                "environmentId": "environment-1",
            }
        }

    monkeypatch.setattr(target, "_graphql", fake_graphql)
    result = target.connections_status_reply()

    assert "Railway account/workspace token (cross-project targets): MISSING" in result
    assert "Railway project token candidate (single project/environment): CONFIGURED" in result
    assert "SLH scoped Railway integration: PASS" in result
    assert "project-token-secret" not in result
    assert calls and all("projectToken" in query for query in calls)


def test_connections_status_blocks_project_token_with_wrong_scope(monkeypatch):
    for key in (
        "SLH_RAILWAY_TOKEN", "RAILWAY_PROJECT_TOKEN", "RAILWAY_PROJECT_TOKEN_SLH",
        "RAILWAY_API_TOKEN", "RAILWAY_API_TOKEN_SLH",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("RAILWAY_TOKEN", "wrong-scope-secret")
    monkeypatch.setenv("SLH_RAILWAY_PROJECT_ID", "expected-project")
    monkeypatch.setenv("SLH_RAILWAY_ENVIRONMENT_ID", "expected-environment")
    monkeypatch.setenv("SLH_RAILWAY_SERVICE_ID", "service-1")

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self):
            return b'{"full_name":"osifeu-prog/slh-bot"}'

    monkeypatch.setattr(
        target.urllib.request, "urlopen",
        lambda request, timeout: Response(),
    )
    monkeypatch.setattr(
        target, "_graphql",
        lambda ctx, query, variables=None: {
            "projectToken": {
                "projectId": "other-project",
                "environmentId": "other-environment",
            }
        },
    )

    result = target.connections_status_reply()

    assert "SLH scoped Railway integration: BLOCKED — RAILWAY_TOKEN_SCOPE_MISMATCH" in result
    assert "wrong-scope-secret" not in result


def test_connections_status_route_is_owner_only_and_private(monkeypatch):
    from types import SimpleNamespace

    class FakeBot:
        def __init__(self):
            self.handlers = {}
            self.replies = []

        def message_handler(self, commands):
            def decorator(fn):
                for command in commands:
                    self.handlers[command] = fn
                return fn
            return decorator

        def reply_to(self, message, text, parse_mode=None):
            self.replies.append((message, text, parse_mode))

    bot = FakeBot()
    target.register(bot)
    monkeypatch.setattr(target, "is_owner", lambda uid: str(uid) == "42")
    monkeypatch.setattr(target, "connections_status_reply", lambda: "SAFE_CONNECTION_REPORT")
    handler = bot.handlers["connections_status"]

    owner_private = SimpleNamespace(
        from_user=SimpleNamespace(id=42),
        chat=SimpleNamespace(type="private"),
        text="/connections_status",
    )
    handler(owner_private)
    assert bot.replies[-1][1] == "SAFE_CONNECTION_REPORT"

    non_owner = SimpleNamespace(
        from_user=SimpleNamespace(id=99),
        chat=SimpleNamespace(type="private"),
        text="/connections_status",
    )
    handler(non_owner)
    assert bot.replies[-1][1] == "⛔ OWNER only"

    owner_group = SimpleNamespace(
        from_user=SimpleNamespace(id=42),
        chat=SimpleNamespace(type="group"),
        text="/connections_status",
    )
    handler(owner_group)
    assert bot.replies[-1][1] == "⛔ Connection status is available in private chat only."
