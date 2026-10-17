"""The read-only system check must not treat an intentionally closed TON gate as a system fault."""
import core.bnb_gate as bnb_gate
import core.system_check as system_check
import core.ton_deposit_service as ton_service


def _prepare(monkeypatch, *, ton_wallet="test-ton-wallet", ton_rate=100):
    def fake_json(path, default=None):
        if path == "state/db.json":
            return {"users": {}, "transactions": [], "ledger": []}
        if path == "state/agents.json":
            return {}
        if path == "control_plane_registry.json":
            return {"canonical": {"repo": "osifeu-prog/slh-bot"}}
        if path == "state/ai_health.json":
            return {}
        return default

    monkeypatch.setattr(system_check, "_json", fake_json)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("ALPHA_INVITE_OPEN", "1")
    monkeypatch.setattr(
        bnb_gate,
        "bnb_readiness",
        lambda: {
            "ready": True,
            "effective_open": False,
            "chain_id": 56,
            "confirmations_required": 15,
            "reasons": [],
        },
    )
    monkeypatch.setattr(
        ton_service,
        "_settings",
        lambda: (ton_wallet, ton_rate),
    )
    monkeypatch.setattr(ton_service, "deposits_are_open", lambda: False)


def test_closed_ton_gate_is_not_a_system_failure_when_configuration_is_valid(monkeypatch):
    _prepare(monkeypatch)

    report = system_check.run_system_checks()
    ton_check = next(check for check in report["checks"] if check["name"] == "ton_gate")

    assert ton_check["status"] == "PASS"
    assert ton_check["open"] is False
    assert ton_check["effective_state"] == "CLOSED"
    assert ton_check["configuration_valid"] is True
    assert "CLOSED is a safe policy state" in ton_check["detail"]


def test_closed_ton_gate_still_fails_when_configuration_is_missing(monkeypatch):
    _prepare(monkeypatch, ton_wallet="", ton_rate=0)

    report = system_check.run_system_checks()
    ton_check = next(check for check in report["checks"] if check["name"] == "ton_gate")

    assert ton_check["status"] == "FAIL"
    assert ton_check["open"] is False
    assert ton_check["effective_state"] == "CLOSED"
    assert ton_check["configuration_valid"] is False
