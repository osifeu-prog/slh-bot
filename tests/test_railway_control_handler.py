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
    monkeypatch.delenv("RAILWAY_TOKEN", raising=False)
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "project")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "environment")
    monkeypatch.setenv("RAILWAY_SERVICE_ID", "service")
    with pytest.raises(RuntimeError, match="RAILWAY_CREDENTIALS_MISSING"):
        target._ids()


def test_status_does_not_print_secrets_when_token_missing(monkeypatch):
    monkeypatch.delenv("RAILWAY_TOKEN", raising=False)
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "project")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "environment")
    monkeypatch.setenv("RAILWAY_SERVICE_ID", "service")
    result = target.railway_status_reply()
    assert "RAILWAY_CREDENTIALS_MISSING" in result
    assert "Bearer " not in result
    assert "token_contract" not in result


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
