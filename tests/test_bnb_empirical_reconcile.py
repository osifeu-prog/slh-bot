from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from handlers import bnb_empirical_handler as target


UID = "8789977826"
TX = "0x" + "ab" * 32
ADDRESS = "0x1111111111111111111111111111111111111111"
TREASURY = "0x2222222222222222222222222222222222222222"
NOW = datetime(2026, 10, 9, 10, 0, tzinfo=timezone.utc)


def _db():
    return {
        "ledger": [],
        "settlement_evidence": {},
        "bnb_empirical_reconcile_pending": {},
        "bnb_empirical_reconcile_audit": [],
    }


def _verified():
    return {
        "ok": True,
        "tx_hash": TX,
        "from": ADDRESS,
        "to": TREASURY,
        "amount_bnb": 0.01,
        "amount_wei": 10**16,
        "confirmations": 20,
        "required_confirmations": 15,
    }


def _patch_valid_preview(monkeypatch, db):
    import core.bnb_gate as gate
    import core.deposit_monitor as monitor
    import core.wallet_binding as binding

    monkeypatch.setattr(target, "is_owner", lambda uid: str(uid) == UID)
    monkeypatch.setattr(target.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(target.state_manager, "atomic_update", lambda mutate: mutate(db))
    monkeypatch.setattr(gate, "bnb_deposits_open", lambda: False)
    monkeypatch.setattr(gate, "bnb_readiness", lambda: {
        "ready": True,
        "effective_open": False,
        "flag_open": False,
        "confirmations_required": 15,
    })
    monkeypatch.setattr(gate, "_effective_config", lambda: {"treasury_wallet": TREASURY})
    monkeypatch.setattr(monitor, "verify_bnb_deposit", lambda tx_hash: _verified())
    monkeypatch.setattr(binding, "get_binding", lambda uid: {"address": ADDRESS})


def test_preview_for_existing_transaction_is_read_only(monkeypatch):
    db = _db()
    _patch_valid_preview(monkeypatch, db)

    with patch("core.bnb_empirical_smoke.run") as settle:
        result = target.prepare_existing_bnb_reconcile(UID, TX, now=NOW)

    assert result["status"] == "PREPARED"
    assert result["amount_wei"] == 10**16
    assert result["confirmations"] == 20
    assert result["estimated_credits"] == 10.0
    assert db["bnb_empirical_reconcile_pending"][UID]["status"] == "PENDING_CONFIRMATION"
    assert db["ledger"] == []
    assert db["settlement_evidence"] == {}
    settle.assert_not_called()


def test_preview_rejects_non_owner_and_invalid_hash(monkeypatch):
    monkeypatch.setattr(target, "is_owner", lambda _uid: False)
    assert target.prepare_existing_bnb_reconcile("42", TX, now=NOW)["status"] == "FORBIDDEN"

    monkeypatch.setattr(target, "is_owner", lambda _uid: True)
    assert target.prepare_existing_bnb_reconcile(UID, "not-a-hash", now=NOW)["status"] == "INVALID_TX_HASH"


def test_preview_rejects_transaction_from_unbound_wallet(monkeypatch):
    db = _db()
    _patch_valid_preview(monkeypatch, db)
    import core.wallet_binding as binding
    monkeypatch.setattr(binding, "get_binding", lambda _uid: {"address": "0x9999999999999999999999999999999999999999"})

    result = target.prepare_existing_bnb_reconcile(UID, TX, now=NOW)

    assert result["status"] == "BNB_TX_SENDER_NOT_BOUND_WALLET"
    assert db["bnb_empirical_reconcile_pending"] == {}


def test_preview_rejects_transaction_already_present_in_ledger(monkeypatch):
    db = _db()
    db["ledger"].append({"meta": {"idempotency_key": f"bnb:deposit:{TX.lower()}"}})
    _patch_valid_preview(monkeypatch, db)

    result = target.prepare_existing_bnb_reconcile(UID, TX, now=NOW)

    assert result["status"] == "ALREADY_SETTLED"
    assert db["bnb_empirical_reconcile_pending"] == {}


def test_confirm_requires_pending_confirmation_and_is_single_use(monkeypatch):
    db = _db()
    _patch_valid_preview(monkeypatch, db)

    assert target.confirm_existing_bnb_reconcile(UID, now=NOW)["status"] == "NOT_PENDING"

    prepared = target.prepare_existing_bnb_reconcile(UID, TX, now=NOW)
    assert prepared["status"] == "PREPARED"

    with patch("core.bnb_empirical_smoke.run", return_value={
        "status": "PASS",
        "tx_hash": TX,
        "credits": 10.0,
        "amount_wei": 10**16,
        "confirmations": 20,
        "gate_remained_closed": True,
    }) as settle:
        result = target.confirm_existing_bnb_reconcile(UID, tx_hash=TX, now=NOW + timedelta(seconds=5))
        replay = target.confirm_existing_bnb_reconcile(UID, tx_hash=TX, now=NOW + timedelta(seconds=6))

    assert result["status"] == "PASS"
    assert result["credits"] == 10.0
    assert result["gate_remained_closed"] is True
    assert replay["status"] in {"ALREADY_HANDLED", "NOT_PENDING"}
    settle.assert_called_once_with(UID, TX)
    assert db["bnb_empirical_reconcile_pending"][UID]["status"] == "PASS"
    assert len(db["bnb_empirical_reconcile_audit"]) == 1


def test_confirm_expires_preview_without_settlement(monkeypatch):
    db = _db()
    _patch_valid_preview(monkeypatch, db)
    assert target.prepare_existing_bnb_reconcile(UID, TX, now=NOW)["status"] == "PREPARED"

    with patch("core.bnb_empirical_smoke.run") as settle:
        result = target.confirm_existing_bnb_reconcile(UID, tx_hash=TX, now=NOW + timedelta(minutes=6))

    assert result["status"] == "EXPIRED"
    settle.assert_not_called()



def test_confirm_requires_exact_tx_hash_match(monkeypatch):
    db = _db()
    _patch_valid_preview(monkeypatch, db)
    assert target.prepare_existing_bnb_reconcile(UID, TX, now=NOW)["status"] == "PREPARED"

    other_tx = "0x" + "cd" * 32
    with patch("core.bnb_empirical_smoke.run") as settle:
        result = target.confirm_existing_bnb_reconcile(UID, tx_hash=other_tx, now=NOW + timedelta(seconds=5))

    assert result["status"] == "TX_HASH_MISMATCH"
    assert db["bnb_empirical_reconcile_pending"][UID]["status"] == "PENDING_CONFIRMATION"
    settle.assert_not_called()
