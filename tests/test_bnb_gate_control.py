"""Close-only BNB gate override behavior.

These tests deliberately stub only the chain-proof boundary. They verify that
policy and operator intent remain fail-closed before any live RPC is involved.
"""
import core.bnb_gate as target


OWNER_UID = "8789977826"


def _db(override=None):
    settings = {"network": "bsc", "chain_id": 56, "rpc": "https://rpc.invalid",
                "treasury_wallet": "0x1111111111111111111111111111111111111111",
                "confirmations": 15}
    if override is not None:
        settings["bnb_deposits_override"] = override
    return {"users": {"1": {}}, "bsc_settings": settings, "wallet_bindings": {},
            "settlement_evidence": {"bnb": {"status": "PASS"}}, "ledger": []}


def _wire_gate(monkeypatch, db, *, ready=True, evidence=True):
    import os
    monkeypatch.setattr(target.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(target, "bnb_readiness", lambda *_a, **_kw: {
        "effective_open": bool(ready), "ready": bool(ready), "reasons": []
    })
    monkeypatch.setattr(target, "_effective_config", lambda *_a, **_kw: {
        "treasury_wallet": db["bsc_settings"]["treasury_wallet"],
        "confirmations": 15,
    })
    monkeypatch.setattr(target, "_empirical_settlement_evidence",
                        lambda *_a, **_kw: {"status": "PASS"})
    monkeypatch.setattr(target, "_empirical_evidence_revalidated",
                        lambda *_a, **_kw: bool(evidence))
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "1")


def test_deny_override_closes_even_when_env_and_evidence_are_green(monkeypatch):
    db = _db("deny")
    _wire_gate(monkeypatch, db, ready=True, evidence=True)

    assert target.bnb_deposits_open() is False


def test_unreadable_db_fails_closed_even_when_env_and_evidence_are_green(monkeypatch):
    _wire_gate(monkeypatch, _db(), ready=True, evidence=True)
    monkeypatch.setattr(target.state_manager, "load_db",
                        lambda: (_ for _ in ()).throw(OSError("db unavailable")))

    assert target.bnb_deposits_open() is False


def test_invalid_db_shape_fails_closed(monkeypatch):
    _wire_gate(monkeypatch, _db(), ready=True, evidence=True)
    monkeypatch.setattr(target.state_manager, "load_db", lambda: None)

    assert target.bnb_deposits_open() is False


def test_allow_override_is_unknown_and_fails_closed_even_when_everything_else_is_green(monkeypatch):
    db = _db("allow")
    _wire_gate(monkeypatch, db, ready=True, evidence=True)
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "1")

    assert target.bnb_deposits_open() is False


def test_unknown_override_value_fails_closed_even_when_everything_else_is_green(monkeypatch):
    db = _db("yes")
    _wire_gate(monkeypatch, db, ready=True, evidence=True)
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "1")

    assert target.bnb_deposits_open() is False


def test_missing_bsc_settings_fail_closed(monkeypatch):
    db = _db()
    db.pop("bsc_settings")
    _wire_gate(monkeypatch, _db(), ready=True, evidence=True)
    monkeypatch.setattr(target.state_manager, "load_db", lambda: db)

    assert target.bnb_deposits_open() is False


def test_readiness_failure_blocks_even_with_env_and_evidence(monkeypatch):
    db = _db()
    _wire_gate(monkeypatch, db, ready=False, evidence=True)

    assert target.bnb_deposits_open() is False


def test_invalid_empirical_evidence_blocks_even_when_env_and_readiness_are_green(monkeypatch):
    db = _db()
    _wire_gate(monkeypatch, db, ready=True, evidence=False)

    assert target.bnb_deposits_open() is False


def test_open_requires_env_readiness_and_revalidated_evidence(monkeypatch):
    db = _db()
    _wire_gate(monkeypatch, db, ready=True, evidence=True)

    assert target.bnb_deposits_open() is True


def test_unresolved_history_prevents_gate_open(monkeypatch):
    db = _db()
    _wire_gate(monkeypatch, db, ready=True, evidence=True)
    monkeypatch.setattr(
        "core.bnb_history_audit.audit_bnb_deposit_history",
        lambda snapshot: {"status": "BLOCKED", "blockers": ["SELF_TRANSFER_NOT_A_DEPOSIT"]},
    )

    assert target.bnb_deposits_open() is False


def test_owner_close_control_requires_confirmation_and_writes_audit(monkeypatch):
    import handlers.bnb_gate_control_handler as control

    db = _db()
    monkeypatch.setattr(control, "is_owner", lambda uid: str(uid) == OWNER_UID)
    monkeypatch.setattr(control.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(control.state_manager, "atomic_update", lambda mutate: mutate(db))

    preview = control._prepare(OWNER_UID, "close")
    assert preview["status"] == "PREPARED"
    assert "bnb_deposits_override" not in db["bsc_settings"]

    result = control._confirm(OWNER_UID, preview["confirmation_id"])
    assert result["status"] == "OK"
    assert db["bsc_settings"]["bnb_deposits_override"] == "deny"
    assert db["bnb_gate_override_audit"][-1]["uid"] == OWNER_UID
    assert db["bnb_gate_override_audit"][-1]["action"] == "deny"


def test_non_owner_cannot_prepare_or_confirm_gate_change(monkeypatch):
    import handlers.bnb_gate_control_handler as control

    db = _db()
    monkeypatch.setattr(control, "is_owner", lambda uid: str(uid) == OWNER_UID)
    monkeypatch.setattr(control.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(control.state_manager, "atomic_update", lambda mutate: mutate(db))

    preview = control._prepare("5010371391", "close")
    assert preview["status"] == "FORBIDDEN"
    result = control._confirm("5010371391", "not-a-confirmation")
    assert result["status"] == "FORBIDDEN"
    assert "bnb_deposits_override" not in db["bsc_settings"]
    assert db.get("bnb_gate_override_audit", []) == []


def test_expired_close_confirmation_cannot_mutate_gate(monkeypatch):
    import handlers.bnb_gate_control_handler as control
    from datetime import timedelta

    db = _db()
    monkeypatch.setattr(control, "is_owner", lambda uid: str(uid) == OWNER_UID)
    monkeypatch.setattr(control.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(control.state_manager, "atomic_update", lambda mutate: mutate(db))

    preview = control._prepare(OWNER_UID, "close")
    control._PENDING[preview["confirmation_id"]]["expires_at"] = (
        control._utc_now() - timedelta(seconds=1)
    )
    result = control._confirm(OWNER_UID, preview["confirmation_id"])

    assert result["status"] == "EXPIRED"
    assert "bnb_deposits_override" not in db["bsc_settings"]
    assert db.get("bnb_gate_override_audit", []) == []


def test_env_closed_cannot_be_overridden_when_readiness_helpers_are_live(monkeypatch):
    import core.bnb_gate as target

    db = _db("allow")
    monkeypatch.setattr(target.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(target, "_effective_config", lambda snapshot=None: {
        "network": "bsc",
        "rpc": "https://rpc.invalid",
        "chain_id": 56,
        "confirmations": 15,
        "treasury_wallet": "0x1111111111111111111111111111111111111111",
    })
    monkeypatch.setattr(target, "_empirical_settlement_evidence", lambda snapshot=None: {"status": "PASS"})
    monkeypatch.setattr(target, "_empirical_evidence_revalidated", lambda *args, **kwargs: True)
    monkeypatch.setenv("SLH_BSC_CANONICAL_TREASURY", "0x1111111111111111111111111111111111111111")
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "0")

    assert target.bnb_readiness(db)["ready"] is True
    assert target.bnb_readiness(db)["effective_open"] is False
    assert target.bnb_deposits_open() is False
