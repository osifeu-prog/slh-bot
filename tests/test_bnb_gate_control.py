"""Fail-closed tests for the owner-controlled BNB gate override."""
from datetime import timedelta

import core.bnb_gate as gate
import handlers.bnb_gate_control_handler as control


def _db(override=None):
    settings = {}
    if override is not None:
        settings["bnb_deposits_override"] = override
    return {"bsc_settings": settings, "wallet_bindings": {}}


def _patch_open_path(monkeypatch, *, db=None, readiness=None, evidence=True):
    monkeypatch.setattr(gate.state_manager, "load_db", lambda: _db() if db is None else db)
    monkeypatch.setattr(
        gate, "bnb_readiness",
        lambda snapshot: {"effective_open": True, "ready": True} if readiness is None else readiness,
    )
    monkeypatch.setattr(gate, "_empirical_settlement_evidence", lambda snapshot: {"status": "PASS"})
    monkeypatch.setattr(gate, "_effective_config", lambda snapshot: {"treasury_wallet": "0x1111111111111111111111111111111111111111"})
    monkeypatch.setattr(gate, "_empirical_evidence_revalidated", lambda empirical, config, db=None: evidence)


def test_db_read_failure_fails_closed(monkeypatch):
    monkeypatch.setattr(gate.state_manager, "load_db", lambda: (_ for _ in ()).throw(RuntimeError("DB_READ_FAILED")))
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "1")
    assert gate.bnb_deposits_open() is False


def test_deny_closes_even_when_env_open(monkeypatch):
    monkeypatch.setattr(gate.state_manager, "load_db", lambda: _db("deny"))
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "1")
    assert gate.bnb_deposits_open() is False


def test_allow_does_not_bypass_env_closed(monkeypatch):
    monkeypatch.setattr(gate.state_manager, "load_db", lambda: _db("allow"))
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "0")
    monkeypatch.setattr(gate, "bnb_readiness", lambda snapshot: {"effective_open": False, "ready": True})
    assert gate.bnb_deposits_open() is False


def test_readiness_failure_blocks_even_when_env_open(monkeypatch):
    _patch_open_path(monkeypatch, readiness={"effective_open": False, "ready": False, "reasons": ["TEST_BLOCKER"]})
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "1")
    assert gate.bnb_deposits_open() is False


def test_invalid_empirical_evidence_blocks(monkeypatch):
    _patch_open_path(monkeypatch, evidence=False)
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "1")
    assert gate.bnb_deposits_open() is False


def test_gate_opens_only_when_env_readiness_and_evidence_pass(monkeypatch):
    _patch_open_path(monkeypatch, evidence=True)
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "1")
    assert gate.bnb_deposits_open() is True


def test_confirm_uid_mismatch_does_not_consume_confirmation(monkeypatch):
    cid = "test-confirm-id"
    control._PENDING[cid] = {
        "uid": "owner-1",
        "action": "close",
        "expires_at": control._utc_now() + timedelta(minutes=5),
    }
    monkeypatch.setattr(control, "is_owner", lambda uid: True)
    result = control._confirm("owner-2", cid)
    assert result["status"] == "UID_MISMATCH"
    assert cid in control._PENDING
    control._PENDING.pop(cid, None)


def test_close_override_is_written_with_audit(monkeypatch):
    db = {"users": {"1": {}}, "bsc_settings": {}, "bnb_gate_override_audit": []}

    def fake_atomic_update(mutate):
        result = mutate(db)
        return result

    monkeypatch.setattr(control.state_manager, "atomic_update", fake_atomic_update)
    result = control._write_override("deny", uid="owner-1")
    assert result == {"status": "OK", "value": "deny"}
    assert db["bsc_settings"]["bnb_deposits_override"] == "deny"
    assert len(db["bnb_gate_override_audit"]) == 1
    assert db["bnb_gate_override_audit"][0]["action"] == "deny"
