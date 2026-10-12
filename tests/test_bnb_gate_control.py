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
    return {"bsc_settings": settings, "wallet_bindings": {},
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


def test_env_closed_cannot_be_overridden_by_allow(monkeypatch):
    db = _db("allow")
    _wire_gate(monkeypatch, db, ready=False, evidence=True)
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "0")

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
