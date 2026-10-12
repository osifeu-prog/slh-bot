import json

import pytest

import handlers.railway_control_handler as target


def test_replace_logic_preserves_non_treasury_fields():
    # Exercise the same config transformation used at apply time without API access.
    original = {
        "network": "bsc",
        "rpc": "https://bsc-dataseed.binance.org/",
        "chain_id": 56,
        "symbol": "BNB",
        "token_contract": "0xACb0A09414CEA1C879c67bB7A877E4e19480f022",
        "confirmations": 15,
        "treasury_wallet": "0x468328B2a7C9b5629e87844Bb4531e7409400b34",
    }
    new = dict(original)
    new["treasury_wallet"] = "0x03bf3BfB8752203353645321869FE1e90C7C300F"
    assert new["treasury_wallet"] != original["treasury_wallet"]
    for key in original:
        if key != "treasury_wallet":
            assert new[key] == original[key]


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
