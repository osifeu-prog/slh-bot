from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from core import credit_adjustment_service as target

UID = "test-owner-1"
TX = "0x" + "ab" * 32
TX2 = "0x" + "cd" * 32
TREASURY = "0x1111111111111111111111111111111111111111"
OWNER_WALLET = "0x2222222222222222222222222222222222222222"
SOURCE_KEY = f"bnb:deposit:{TX}"
CORRECTION_KEY = f"accounting:reversal:{TX}"


def _db():
    return {
        "users": {UID: {"wallet": {"credits": 30.072775}}},
        "wallet_bindings": {
            "bsc:test-owner": {"uid": UID, "chain": "bsc", "address": OWNER_WALLET}
        },
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
                    "from": OWNER_WALLET,
                    "to": OWNER_WALLET,
                },
            },
            {
                "time": "2026-10-12T13:13:32+00:00",
                "uid": UID,
                "before": 18.091775,
                "amount": 10.0,
                "after": 28.091775,
                "reason": "bnb:deposit",
                "meta": {
                    "tx_hash": TX2,
                    "idempotency_key": f"bnb:deposit:{TX2}",
                    "bnb_amount_wei": 10**16,
                    "from": OWNER_WALLET,
                    "to": TREASURY,
                },
            },
            {
                "time": "2026-10-12T13:20:00+00:00",
                "uid": UID,
                "before": 28.091775,
                "amount": 0.99,
                "after": 29.081775,
                "reason": "exchange:settlement_credits",
                "meta": {"trade_id": "T-1"},
            },
            {
                "time": "2026-10-12T13:25:00+00:00",
                "uid": UID,
                "before": 29.081775,
                "amount": 0.991,
                "after": 30.072775,
                "reason": "exchange:settlement_credits",
                "meta": {"trade_id": "T-2"},
            },
        ],
        "credit_adjustment_audit": [],
        "bsc_settings": {
            "chain_id": 56,
            "rpc": "https://rpc.invalid",
            "treasury_wallet": TREASURY,
            "confirmations": 15,
        },
    }


def _proof():
    return {
        "tx_hash": TX,
        "chain_id": 56,
        "receipt_status": 1,
        "from": OWNER_WALLET,
        "to": OWNER_WALLET,
        "treasury": TREASURY,
        "bound_wallet": OWNER_WALLET,
        "amount_wei": 10**16,
        "block": 123,
        "confirmations": 20,
        "required_confirmations": 15,
    }


def _patch_runtime(monkeypatch, db, proof=None):
    monkeypatch.setenv("SLH_BSC_CANONICAL_TREASURY", TREASURY)
    monkeypatch.setattr(target, "is_owner", lambda actor: str(actor) == UID)
    monkeypatch.setattr(target, "bnb_deposits_open", lambda: False)
    monkeypatch.setattr(target, "_effective_config", lambda _db: db["bsc_settings"])
    proof_state = proof if proof is not None else _proof()
    monkeypatch.setattr(
        target, "_verify_self_transfer_for_reversal",
        lambda _uid, _tx, _snapshot: dict(proof_state),
    )
    monkeypatch.setattr(target.state_manager, "atomic_update", lambda mutate: mutate(db))
    monkeypatch.setattr(target, "is_quarantined_bsc_address", lambda _address: False)
    return proof_state


def _apply(db, expected="30.072775"):
    return target.reverse_invalid_bnb_deposit(
        actor_uid=UID,
        uid=UID,
        tx_hash=TX,
        expected_current_balance=expected,
        now=datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc),
    )


def test_reversal_claws_back_source_amount_without_rewriting_later_activity(monkeypatch):
    db = _db()
    original = deepcopy(db["ledger"])
    _patch_runtime(monkeypatch, db)

    result = _apply(db)

    assert result["status"] == "APPLIED"
    assert result["amount_reversed"] == 10.0
    assert result["balance_before"] == 30.072775
    assert result["balance_after"] == 20.072775
    assert result["gate_remained_closed"] is True
    assert db["users"][UID]["wallet"]["credits"] == 20.072775
    assert db["ledger"][:-1] == original
    reversal = db["ledger"][-1]
    assert reversal["reason"] == "accounting:invalid_bnb_deposit_reversal"
    assert reversal["amount"] == -10.0
    assert reversal["before"] == 30.072775
    assert reversal["after"] == 20.072775
    assert reversal["meta"]["correction_version"] == 2
    assert reversal["meta"]["source_idempotency_key"] == SOURCE_KEY
    assert reversal["meta"]["idempotency_key"] == CORRECTION_KEY
    assert reversal["meta"]["from"] == OWNER_WALLET
    assert reversal["meta"]["to"] == OWNER_WALLET
    assert len(db["credit_adjustment_audit"]) == 1


def test_reversal_is_idempotent_after_more_chain_confirmations(monkeypatch):
    db = _db()
    proof = _proof()
    _patch_runtime(monkeypatch, db, proof)

    first = _apply(db)
    proof["confirmations"] = 100
    second = _apply(db)

    assert first["status"] == "APPLIED"
    assert second["status"] == "ALREADY_REVERSED"
    assert db["users"][UID]["wallet"]["credits"] == 20.072775
    assert len(db["ledger"]) == 5
    assert len(db["credit_adjustment_audit"]) == 1


def test_stale_balance_fails_without_mutation(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)

    with pytest.raises(ValueError, match="CURRENT_BALANCE_MISMATCH"):
        _apply(db, expected="30.072774")

    assert db == before


def test_later_ledger_sequence_mismatch_fails_without_mutation(monkeypatch):
    db = _db()
    db["ledger"][2]["before"] = 99.0
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)

    with pytest.raises(ValueError, match="ACCOUNT_LEDGER_SEQUENCE_INVALID"):
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
            expected_current_balance="30.072775",
        )

    assert db == before


def test_open_bnb_gate_blocks_correction(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)
    monkeypatch.setattr(target, "bnb_deposits_open", lambda: True)

    with pytest.raises(ValueError, match="BNB_GATE_MUST_REMAIN_CLOSED"):
        _apply(db)

    assert db == before


def test_source_that_is_not_a_self_transfer_is_rejected(monkeypatch):
    db = _db()
    before = deepcopy(db)
    proof = {**_proof(), "to": TREASURY}
    _patch_runtime(monkeypatch, db, proof)

    with pytest.raises(ValueError, match="SOURCE_NOT_BOUND_WALLET_SELF_TRANSFER"):
        _apply(db)

    assert db == before


def test_duplicate_source_idempotency_key_fails_closed(monkeypatch):
    db = _db()
    db["ledger"].append(deepcopy(db["ledger"][0]))
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)

    with pytest.raises(ValueError, match="SOURCE_DEPOSIT_NOT_UNIQUE"):
        _apply(db)

    assert db == before


def test_existing_reversal_with_corrupt_audit_fails_closed(monkeypatch):
    db = _db()
    _patch_runtime(monkeypatch, db)
    assert _apply(db)["status"] == "APPLIED"
    db["credit_adjustment_audit"][0]["balance_after"] = 999
    before = deepcopy(db)

    with pytest.raises(ValueError, match="REVERSAL_AUDIT_RECONCILIATION_FAILED"):
        _apply(db)

    assert db == before
