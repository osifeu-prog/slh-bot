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



def test_auto_discovery_prepares_preview_for_one_exact_existing_transfer_without_settlement(monkeypatch):
    discovery = {
        "status": "FOUND",
        "candidate": {"tx_hash": TX},
        "candidates": [{"tx_hash": TX}],
        "provider": "test",
        "scope": "read_only_discovery",
    }
    preview = {"status": "PREPARED", "tx_hash": TX, "reconcile_id": "preview-1"}

    with patch(
        "core.bnb_auto_discovery.discover_bnb_transfer",
        return_value=discovery,
    ) as discover, patch.object(
        target,
        "prepare_existing_bnb_reconcile",
        return_value=preview,
    ) as prepare, patch(
        "core.bnb_empirical_smoke.run"
    ) as settle:
        result = target.prepare_auto_existing_bnb_reconcile(UID, now=NOW)

    assert result == preview
    discover.assert_called_once_with(UID)
    prepare.assert_called_once_with(UID, TX, now=NOW)
    settle.assert_not_called()


def test_auto_discovery_returns_not_found_without_creating_preview_or_settlement(monkeypatch):
    discovery = {
        "status": "NOT_FOUND",
        "scope": "read_only_discovery",
        "candidates": [],
    }

    with patch(
        "core.bnb_auto_discovery.discover_bnb_transfer",
        return_value=discovery,
    ) as discover, patch.object(
        target,
        "prepare_existing_bnb_reconcile",
    ) as prepare, patch(
        "core.bnb_empirical_smoke.run"
    ) as settle:
        result = target.prepare_auto_existing_bnb_reconcile(UID, now=NOW)

    assert result["status"] == "NOT_FOUND"
    assert result["candidates"] == []
    discover.assert_called_once_with(UID)
    prepare.assert_not_called()
    settle.assert_not_called()


def test_auto_discovery_fails_closed_on_ambiguous_existing_transfers(monkeypatch):
    discovery = {
        "status": "AMBIGUOUS",
        "scope": "read_only_discovery",
        "candidates": [{"tx_hash": TX}, {"tx_hash": "0x" + "cd" * 32}],
    }

    with patch(
        "core.bnb_auto_discovery.discover_bnb_transfer",
        return_value=discovery,
    ) as discover, patch.object(
        target,
        "prepare_existing_bnb_reconcile",
    ) as prepare, patch(
        "core.bnb_empirical_smoke.run"
    ) as settle:
        result = target.prepare_auto_existing_bnb_reconcile(UID, now=NOW)

    assert result["status"] == "AMBIGUOUS"
    assert len(result["candidates"]) == 2
    discover.assert_called_once_with(UID)
    prepare.assert_not_called()
    settle.assert_not_called()


def test_auto_discovery_requires_owner_before_querying_chain(monkeypatch):
    monkeypatch.setattr(target, "is_owner", lambda _uid: False)

    with patch("core.bnb_auto_discovery.discover_bnb_transfer") as discover:
        result = target.prepare_auto_existing_bnb_reconcile("42", now=NOW)

    assert result["status"] == "FORBIDDEN"
    discover.assert_not_called()



def test_auto_discovery_revalidates_existing_credited_tx_without_new_credits(monkeypatch):
    discovery = {
        "status": "FOUND",
        "candidate": {"tx_hash": TX},
        "candidates": [{"tx_hash": TX}],
        "scope": "read_only_discovery",
    }
    proof = {
        "status": "PASS",
        "tx_hash": TX,
        "credits": 10.0,
        "gate_remained_closed": True,
        "settlement_result_idempotent": True,
        "settlement_result_status": "DUPLICATE",
    }

    with patch(
        "core.bnb_auto_discovery.discover_bnb_transfer",
        return_value=discovery,
    ) as discover, patch.object(
        target,
        "prepare_existing_bnb_reconcile",
        return_value={"status": "ALREADY_SETTLED", "tx_hash": TX},
    ) as prepare, patch(
        "core.bnb_empirical_smoke.reconcile_existing_settlement",
        return_value=proof,
    ) as reconcile, patch(
        "core.bnb_empirical_smoke.run"
    ) as first_pass:
        result = target.prepare_auto_existing_bnb_reconcile(UID, now=NOW)

    assert result["status"] == "PASS"
    assert result["gate_remained_closed"] is True
    assert result["settlement_result_idempotent"] is True
    discover.assert_called_once_with(UID)
    prepare.assert_called_once_with(UID, TX, now=NOW)
    reconcile.assert_called_once_with(UID, TX)
    first_pass.assert_not_called()


def test_auto_preview_reply_uses_real_newlines_for_pass():
    message = target._auto_preview_reply({
        "status": "PASS",
        "tx_hash": TX,
        "gate_remained_closed": True,
    })

    assert "\n" in message
    assert "\\n" not in message
