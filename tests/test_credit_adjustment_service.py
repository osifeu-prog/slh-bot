"""Regression tests for the dormant owner-only BNB self-transfer credit reversal."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from unittest.mock import Mock, patch

import pytest

from core import credit_adjustment_service as target


UID = "test-owner-1"
TX = "0x" + "ab" * 32
TREASURY = "0x1111111111111111111111111111111111111111"
SOURCE_KEY = f"bnb:deposit:{TX}"
CORRECTION_KEY = f"accounting:reversal:{TX}"


def _db():
    return {
        "users": {UID: {"wallet": {"credits": 18.091775}}},
        "ledger": [
            {
                "time": "2026-10-10T08:58:47.536038+00:00",
                "uid": UID,
                "before": 8.091775,
                "amount": 10.0,
                "after": 18.091775,
                "reason": "bnb:deposit",
                "meta": {
                    "tx_hash": TX,
                    "idempotency_key": SOURCE_KEY,
                    "bnb_amount_wei": 10**16,
                    "from": TREASURY,
                    "to": TREASURY,
                },
            }
        ],
        "credit_adjustment_audit": [],
        "bsc_settings": {
            "chain_id": 56,
            "rpc": "https://rpc.invalid",
            "treasury_wallet": TREASURY,
        },
    }


def _proof():
    return {
        "tx_hash": TX,
        "chain_id": 56,
        "receipt_status": 1,
        "from": TREASURY,
        "to": TREASURY,
        "treasury": TREASURY,
        "amount_wei": 10**16,
        "block": 123,
        "confirmations": 20,
        "required_confirmations": 15,
    }


def _patch_runtime(monkeypatch, db):
    monkeypatch.setenv("SLH_BSC_CANONICAL_TREASURY", TREASURY)
    monkeypatch.setattr(target, "is_owner", lambda actor: str(actor) == UID)
    monkeypatch.setattr(target.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(target.state_manager, "atomic_update", lambda mutate: mutate(db))
    monkeypatch.setattr(target, "bnb_deposits_open", lambda: False)
    monkeypatch.setattr(target, "_verify_self_transfer_for_reversal", lambda tx, snapshot: _proof())


def _apply(db, expected="18.091775"):
    return target.reverse_invalid_bnb_deposit(
        actor_uid=UID,
        uid=UID,
        tx_hash=TX,
        expected_current_balance=expected,
        now=datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc),
    )


def test_reversal_appends_audited_compensation_without_editing_source(monkeypatch):
    db = _db()
    original_source = deepcopy(db["ledger"][0])
    _patch_runtime(monkeypatch, db)

    result = _apply(db)

    assert result["status"] == "APPLIED"
    assert result["amount_reversed"] == 10.0
    assert result["balance_before"] == 18.091775
    assert result["balance_after"] == 8.091775
    assert result["gate_remained_closed"] is True
    assert db["users"][UID]["wallet"]["credits"] == 8.091775
    assert db["ledger"][0] == original_source
    assert len(db["ledger"]) == 2
    assert db["ledger"][1]["reason"] == "accounting:invalid_bnb_deposit_reversal"
    assert abs(db["ledger"][1]["amount"] + 10.0) < 1e-9
    assert abs((db["ledger"][1]["before"] + db["ledger"][1]["amount"]) - db["ledger"][1]["after"]) < 1e-9
    assert db["ledger"][1]["meta"]["nominal_credits_reversed"] == 10.0
    assert db["ledger"][1]["meta"]["source_idempotency_key"] == SOURCE_KEY
    assert db["ledger"][1]["meta"]["idempotency_key"] == CORRECTION_KEY
    assert len(db["credit_adjustment_audit"]) == 1


def test_repeated_reversal_is_idempotent(monkeypatch):
    db = _db()
    _patch_runtime(monkeypatch, db)

    first = _apply(db)
    second = _apply(db)

    assert first["status"] == "APPLIED"
    assert second["status"] == "ALREADY_REVERSED"
    assert db["users"][UID]["wallet"]["credits"] == 8.091775
    assert len(db["ledger"]) == 2
    assert len(db["credit_adjustment_audit"]) == 1



def test_existing_reversal_with_inconsistent_audit_fails_closed(monkeypatch):
    db = _db()
    _patch_runtime(monkeypatch, db)
    assert _apply(db)["status"] == "APPLIED"
    db["credit_adjustment_audit"][0]["balance_after"] = 999
    corrupted = deepcopy(db)

    with pytest.raises(ValueError, match="CREDIT_ADJUSTMENT_IDEMPOTENCY_CONFLICT"):
        _apply(db)

    assert db == corrupted


@pytest.mark.parametrize(
    ("location", "field", "bad_value"),
    [
        ("meta", "block", 124),
        ("audit", "block", 124),
        ("meta", "confirmations", 19),
        ("audit", "confirmations", 19),
        ("meta", "required_confirmations", 16),
        ("audit", "required_confirmations", 16),
        ("meta", "amount_wei", "not-an-integer"),
        ("meta", "amount_wei", True),
        ("audit", "block", "not-an-integer"),
    ],
)
def test_existing_reversal_with_corrupt_chain_metadata_fails_closed(
    monkeypatch, location, field, bad_value
):
    db = _db()
    _patch_runtime(monkeypatch, db)
    assert _apply(db)["status"] == "APPLIED"

    row = db["ledger"][1]["meta"] if location == "meta" else db["credit_adjustment_audit"][0]
    row[field] = bad_value
    corrupted = deepcopy(db)

    with pytest.raises(ValueError, match="CREDIT_ADJUSTMENT_IDEMPOTENCY_CONFLICT"):
        _apply(db)

    assert db == corrupted


@pytest.mark.parametrize(
    ("location", "field", "bad_value"),
    [
        ("source_meta", "from", "0x2222222222222222222222222222222222222222"),
        ("source_meta", "to", "0x2222222222222222222222222222222222222222"),
        ("correction_meta", "treasury", "0x2222222222222222222222222222222222222222"),
        ("source_meta", "bnb_amount_wei", 2 * 10**16),
        ("source", "amount", 9.0),
        ("source", "after", 18.5),
        ("correction", "amount", -9.0),
    ],
)
def test_existing_reversal_with_corrupt_treasury_or_credit_math_fails_closed(
    monkeypatch, location, field, bad_value
):
    db = _db()
    _patch_runtime(monkeypatch, db)
    assert _apply(db)["status"] == "APPLIED"

    if location == "source_meta":
        row = db["ledger"][0]["meta"]
    elif location == "correction_meta":
        row = db["ledger"][1]["meta"]
    elif location == "source":
        row = db["ledger"][0]
    else:
        row = db["ledger"][1]
    row[field] = bad_value
    corrupted = deepcopy(db)

    with pytest.raises(ValueError, match="CREDIT_ADJUSTMENT_IDEMPOTENCY_CONFLICT"):
        _apply(db)

    assert db == corrupted


def test_malformed_audit_fails_before_any_in_memory_mutation(monkeypatch):
    db = _db()
    db["credit_adjustment_audit"] = {"unexpected": "object"}
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)

    with pytest.raises(ValueError, match="CREDIT_ADJUSTMENT_AUDIT_UNREADABLE"):
        _apply(db)

    assert db == before


def _patch_file_backed_runtime(monkeypatch, db_path):
    monkeypatch.setenv("SLH_BSC_CANONICAL_TREASURY", TREASURY)
    monkeypatch.setattr(target, "is_owner", lambda actor: str(actor) == UID)
    monkeypatch.setattr(target, "bnb_deposits_open", lambda: False)
    monkeypatch.setattr(target, "_verify_self_transfer_for_reversal", lambda tx, snapshot: _proof())
    monkeypatch.setattr(target.state_manager, "DB_FILE", str(db_path))
    monkeypatch.setattr(target.state_manager, "_LOCK_PATH", str(db_path) + ".lock")
    monkeypatch.setattr(target.state_manager, "_ensure_backup_scheduler", lambda: None)
    monkeypatch.setattr(target.state_manager, "_notify_owner", lambda _message: None)


def test_real_atomic_update_persists_reversal_to_temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "db.json"
    original = _db()
    db_path.write_text(json.dumps(original), encoding="utf-8")
    _patch_file_backed_runtime(monkeypatch, db_path)

    result = _apply(original)

    persisted = json.loads(db_path.read_text(encoding="utf-8"))
    assert result["status"] == "APPLIED"
    assert persisted["users"][UID]["wallet"]["credits"] == 8.091775
    assert len(persisted["ledger"]) == 2
    assert len(persisted["credit_adjustment_audit"]) == 1
    assert persisted["ledger"][0] == original["ledger"][0]


def test_post_replace_save_error_is_reconciled_from_disk_not_blindly_retried(
    monkeypatch, tmp_path
):
    db_path = tmp_path / "db.json"
    original = _db()
    db_path.write_text(json.dumps(original), encoding="utf-8")
    _patch_file_backed_runtime(monkeypatch, db_path)
    real_write = target.state_manager._atomic_write_json_unlocked

    def write_then_raise(path, data):
        real_write(path, data)
        raise OSError("injected post-replace failure")

    monkeypatch.setattr(
        target.state_manager, "_atomic_write_json_unlocked", write_then_raise
    )
    with pytest.raises(OSError, match="injected post-replace failure"):
        _apply(original)

    # The caller sees an error, but atomic replace already committed. Read disk
    # before deciding what to do; the next idempotent call must not debit twice.
    persisted = json.loads(db_path.read_text(encoding="utf-8"))
    assert persisted["users"][UID]["wallet"]["credits"] == 8.091775
    assert len(persisted["ledger"]) == 2
    assert len(persisted["credit_adjustment_audit"]) == 1

    monkeypatch.setattr(
        target.state_manager, "_atomic_write_json_unlocked", real_write
    )
    retry = _apply(persisted)
    assert retry["status"] == "ALREADY_REVERSED"
    reloaded = json.loads(db_path.read_text(encoding="utf-8"))
    assert reloaded["users"][UID]["wallet"]["credits"] == 8.091775
    assert len(reloaded["ledger"]) == 2
    assert len(reloaded["credit_adjustment_audit"]) == 1


def test_stale_balance_fails_without_mutation(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)

    with pytest.raises(ValueError, match="CURRENT_BALANCE_MISMATCH"):
        _apply(db, expected="18.091774")

    assert db == before


def test_later_owner_ledger_activity_fails_without_mutation(monkeypatch):
    db = _db()
    db["ledger"].append({
        "uid": UID, "reason": "exchange:settlement_credits",
        "amount": 1.0, "before": 18.091775, "after": 19.091775,
    })
    db["users"][UID]["wallet"]["credits"] = 19.091775
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)

    with pytest.raises(ValueError, match="OWNER_LEDGER_CHANGED_AFTER_SOURCE_DEPOSIT"):
        _apply(db, expected="19.091775")

    assert db == before


@pytest.mark.parametrize(
    "invalid_wei",
    [True, 1.5, -1, "not-an-integer"],
)
def test_initial_reversal_rejects_non_integer_source_amount_metadata_without_mutation(
    monkeypatch, invalid_wei
):
    db = _db()
    db["ledger"][0]["meta"]["bnb_amount_wei"] = invalid_wei
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)
    monkeypatch.setattr(
        target,
        "_verify_self_transfer_for_reversal",
        lambda *_args: (_ for _ in ()).throw(AssertionError("chain verifier must not run")),
    )

    with pytest.raises(ValueError, match="SOURCE_DEPOSIT_INVALID"):
        _apply(db)

    assert db == before


def test_non_owner_cannot_reverse(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)

    with pytest.raises(PermissionError, match="OWNER_ONLY"):
        target.reverse_invalid_bnb_deposit(
            actor_uid="not-owner",
            uid=UID,
            tx_hash=TX,
            expected_current_balance="18.091775",
        )

    assert db == before



def _web3_stub(fake_w3):
    class StubWeb3:
        HTTPProvider = staticmethod(
            lambda _rpc, request_kwargs=None: object()
        )

        def __new__(cls, *_args, **_kwargs):
            return fake_w3

    return StubWeb3


def _fake_web3_transaction(*, sender=TREASURY, recipient=TREASURY, status=1, value=10**16, block=100):
    fake = Mock()
    fake.eth.chain_id = 56
    fake.eth.block_number = 200
    fake.eth.get_transaction.return_value = {
        "hash": TX,
        "from": sender,
        "to": recipient,
        "value": value,
    }
    fake.eth.get_transaction_receipt.return_value = {
        "status": status,
        "blockNumber": block,
    }
    return fake


def test_live_forensic_verifier_proves_confirmed_canonical_treasury_self_transfer(monkeypatch):
    fake = _fake_web3_transaction()
    config = {
        "chain_id": 56,
        "rpc": "https://rpc.invalid",
        "treasury_wallet": TREASURY,
        "confirmations": 15,
    }
    monkeypatch.setattr(target, "_effective_config", lambda _db: config)
    monkeypatch.setattr(target, "is_quarantined_bsc_address", lambda _address: False)
    monkeypatch.setattr(target, "Web3", _web3_stub(fake))

    with patch.dict(os.environ, {"SLH_BSC_CANONICAL_TREASURY": TREASURY}, clear=False):
        proof = target._verify_self_transfer_for_reversal(TX, _db())

    assert proof["tx_hash"] == TX
    assert proof["chain_id"] == 56
    assert proof["from"].lower() == TREASURY.lower()
    assert proof["to"].lower() == TREASURY.lower()
    assert proof["amount_wei"] == 10**16
    assert proof["confirmations"] == 101
    fake.eth.get_transaction.assert_called_once_with(TX)
    fake.eth.get_transaction_receipt.assert_called_once_with(TX)


def test_live_forensic_verifier_rejects_external_sender(monkeypatch):
    external = "0x2222222222222222222222222222222222222222"
    fake = _fake_web3_transaction(sender=external)
    config = {
        "chain_id": 56,
        "rpc": "https://rpc.invalid",
        "treasury_wallet": TREASURY,
        "confirmations": 15,
    }
    monkeypatch.setattr(target, "_effective_config", lambda _db: config)
    monkeypatch.setattr(target, "is_quarantined_bsc_address", lambda _address: False)
    monkeypatch.setattr(target, "Web3", _web3_stub(fake))

    with patch.dict(os.environ, {"SLH_BSC_CANONICAL_TREASURY": TREASURY}, clear=False):
        with pytest.raises(ValueError, match="BNB_TX_NOT_TREASURY_SELF_TRANSFER"):
            target._verify_self_transfer_for_reversal(TX, _db())


def test_live_forensic_verifier_rejects_failed_receipt(monkeypatch):
    fake = _fake_web3_transaction(status=0)
    config = {
        "chain_id": 56,
        "rpc": "https://rpc.invalid",
        "treasury_wallet": TREASURY,
        "confirmations": 15,
    }
    monkeypatch.setattr(target, "_effective_config", lambda _db: config)
    monkeypatch.setattr(target, "is_quarantined_bsc_address", lambda _address: False)
    monkeypatch.setattr(target, "Web3", _web3_stub(fake))

    with patch.dict(os.environ, {"SLH_BSC_CANONICAL_TREASURY": TREASURY}, clear=False):
        with pytest.raises(ValueError, match="BNB_TX_NOT_SUCCESSFUL"):
            target._verify_self_transfer_for_reversal(TX, _db())



def test_reversal_accepts_canonical_float_rounding_for_non_round_bnb_amount(monkeypatch):
    from decimal import Decimal

    db = _db()
    amount_wei = 123456789012345678
    credits = float(Decimal(amount_wei) * Decimal("1000") / Decimal(10**18))
    before = 8.091775
    after = before + credits
    source = db["ledger"][0]
    source["before"] = before
    source["amount"] = credits
    source["after"] = after
    source["meta"]["bnb_amount_wei"] = amount_wei
    db["users"][UID]["wallet"]["credits"] = after
    proof = {**_proof(), "amount_wei": amount_wei}
    _patch_runtime(monkeypatch, db)
    monkeypatch.setattr(target, "_verify_self_transfer_for_reversal", lambda _tx, _db: proof)

    result = target.reverse_invalid_bnb_deposit(
        actor_uid=UID,
        uid=UID,
        tx_hash=TX,
        expected_current_balance=str(after),
    )

    assert result["status"] == "APPLIED"
    assert result["amount_reversed"] == credits
    assert db["users"][UID]["wallet"]["credits"] == before
