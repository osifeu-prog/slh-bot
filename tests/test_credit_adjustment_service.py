from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from core import credit_adjustment_service as target
from core import bnb_history_audit

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
                    "block": 123,
                    "confirmations": 20,
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
    # Every correction fixture starts from an explicitly operator-closed gate.
    # Individual tests override/delete this value to exercise fail-closed cases.
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "0")
    monkeypatch.setattr(target, "is_owner", lambda actor: str(actor) == UID)
    monkeypatch.setattr(target, "bnb_deposits_open", lambda: False)
    monkeypatch.setattr(target, "_effective_config", lambda _db: db["bsc_settings"])
    proof_state = proof if proof is not None else _proof()
    monkeypatch.setattr(
        target, "_verify_self_transfer_for_reversal",
        lambda _uid, _tx, _snapshot: dict(proof_state),
    )
    monkeypatch.setattr(target.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(target.state_manager, "atomic_update", lambda mutate: mutate(db))
    monkeypatch.setattr(target, "is_quarantined_bsc_address", lambda _address: False)
    monkeypatch.setattr(
        bnb_history_audit,
        "audit_bnb_deposit_history",
        lambda _db: {
            "scope": "read_only",
            "status": "BLOCKED",
            "rows_found": 2,
            "rows_checked": 2,
            "failed_rows": 1,
            "blockers": [
                "SELF_TRANSFER_NOT_A_DEPOSIT",
                "HISTORICAL_DESTINATION_NOT_CURRENT_TREASURY",
            ],
            "findings": [
                {
                    "tx_suffix": TX[-8:],
                    "status": "BLOCKED",
                    "issues": [
                        "SELF_TRANSFER_NOT_A_DEPOSIT",
                        "HISTORICAL_DESTINATION_NOT_CURRENT_TREASURY",
                    ],
                },
                {"tx_suffix": TX2[-8:], "status": "PASS", "issues": []},
            ],
        },
    )
    return proof_state


def _apply(db, expected="30.072775"):
    return target.reverse_invalid_bnb_deposit(
        actor_uid=UID,
        uid=UID,
        tx_hash=TX,
        expected_current_balance=expected,
        now=datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc),
    )


def test_read_only_preview_shows_current_and_projected_balance_without_mutation(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)

    result = target.preview_invalid_bnb_deposit_reversal(
        actor_uid=UID, uid=UID, tx_hash=TX
    )

    assert result["status"] == "PREPARED"
    assert result["scope"] == "read_only"
    assert result["source_ledger_index"] == 0
    assert result["tx_suffix"] == TX[-8:]
    assert result["amount_reversed"] == 10.0
    assert result["balance_before"] == 30.072775
    assert result["balance_after"] == 20.072775
    assert result["gate_remained_closed"] is True
    assert result["database_changed"] is False
    assert result["settlement_executed"] is False
    assert db == before


def test_preview_is_owner_only_and_cannot_target_another_uid(monkeypatch):
    db = _db()
    _patch_runtime(monkeypatch, db)

    with pytest.raises(PermissionError, match="OWNER_ONLY"):
        target.preview_invalid_bnb_deposit_reversal(
            actor_uid="not-owner", uid="not-owner", tx_hash=TX
        )
    with pytest.raises(PermissionError, match="OWNER_SELF_ACCOUNT_ONLY"):
        target.preview_invalid_bnb_deposit_reversal(
            actor_uid=UID, uid="other-user", tx_hash=TX
        )


def test_preview_refuses_when_operator_flag_could_auto_open_gate(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "1")

    with pytest.raises(ValueError, match="BNB_DEPOSITS_FLAG_MUST_BE_CLOSED"):
        target.preview_invalid_bnb_deposit_reversal(
            actor_uid=UID, uid=UID, tx_hash=TX
        )

    assert db == before


def test_preview_blocks_when_row_210_or_another_historical_bnb_row_needs_review(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)
    monkeypatch.setattr(
        bnb_history_audit,
        "audit_bnb_deposit_history",
        lambda _db: {
            "status": "BLOCKED",
            "findings": [
                {
                    "tx_suffix": TX[-8:],
                    "status": "BLOCKED",
                    "issues": [
                        "SELF_TRANSFER_NOT_A_DEPOSIT",
                        "HISTORICAL_DESTINATION_NOT_CURRENT_TREASURY",
                    ],
                },
                {
                    "tx_suffix": TX2[-8:],
                    "status": "BLOCKED",
                    "issues": ["STORED_AMOUNT_WEI_MISMATCH"],
                },
            ],
        },
    )

    with pytest.raises(ValueError, match="HISTORICAL_BNB_AUDIT_HAS_OTHER_BLOCKERS"):
        target.preview_invalid_bnb_deposit_reversal(
            actor_uid=UID, uid=UID, tx_hash=TX
        )
    assert db == before


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


def test_correction_rechecks_raw_gate_flag_inside_atomic_mutation(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)

    def flip_flag_then_mutate(mutate):
        monkeypatch.setenv("BNB_DEPOSITS_OPEN", "1")
        return mutate(db)

    monkeypatch.setattr(target.state_manager, "atomic_update", flip_flag_then_mutate)
    with pytest.raises(ValueError, match="BNB_DEPOSITS_FLAG_MUST_BE_CLOSED"):
        _apply(db)

    assert db == before


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


def test_owner_cannot_reverse_another_users_account(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)

    with pytest.raises(PermissionError, match="OWNER_SELF_ACCOUNT_ONLY"):
        target.reverse_invalid_bnb_deposit(
            actor_uid=UID,
            uid="other-user",
            tx_hash=TX,
            expected_current_balance="30.072775",
        )

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


def test_preview_requires_explicit_closed_flag_when_flag_is_unset(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)
    monkeypatch.delenv("BNB_DEPOSITS_OPEN", raising=False)

    with pytest.raises(ValueError, match="BNB_DEPOSITS_FLAG_MUST_BE_CLOSED"):
        target.preview_invalid_bnb_deposit_reversal(
            actor_uid=UID, uid=UID, tx_hash=TX
        )

    assert db == before


def test_preview_rejects_invalid_raw_bnb_gate_flag(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "false")

    with pytest.raises(ValueError, match="BNB_DEPOSITS_FLAG_MUST_BE_CLOSED"):
        target.preview_invalid_bnb_deposit_reversal(
            actor_uid=UID, uid=UID, tx_hash=TX
        )

    assert db == before


def test_open_bnb_gate_blocks_correction(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "0")
    monkeypatch.setattr(target, "bnb_deposits_open", lambda: True)

    with pytest.raises(ValueError, match="BNB_GATE_MUST_REMAIN_CLOSED"):
        _apply(db)

    assert db == before


def test_reversal_blocks_if_another_historical_deposit_fails_audit(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)
    monkeypatch.setattr(
        bnb_history_audit,
        "audit_bnb_deposit_history",
        lambda _db: {
            "status": "BLOCKED",
            "rows_found": 2,
            "rows_checked": 2,
            "failed_rows": 2,
            "blockers": [
                "SELF_TRANSFER_NOT_A_DEPOSIT",
                "HISTORICAL_DESTINATION_NOT_CURRENT_TREASURY",
                "LEDGER_CREDITS_MISMATCH",
            ],
            "findings": [
                {
                    "tx_suffix": TX[-8:],
                    "status": "BLOCKED",
                    "issues": [
                        "SELF_TRANSFER_NOT_A_DEPOSIT",
                        "HISTORICAL_DESTINATION_NOT_CURRENT_TREASURY",
                    ],
                },
                {
                    "tx_suffix": TX2[-8:],
                    "status": "BLOCKED",
                    "issues": ["LEDGER_CREDITS_MISMATCH"],
                },
            ],
        },
    )

    with pytest.raises(ValueError, match="HISTORICAL_BNB_AUDIT_HAS_OTHER_BLOCKERS"):
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



def test_existing_reversal_by_different_owner_uid_is_not_reported_as_already_reversed(monkeypatch):
    db = _db()
    _patch_runtime(monkeypatch, db)
    other_owner = "another-authorized-owner"
    monkeypatch.setattr(
        target, "is_owner", lambda actor: str(actor) in {UID, other_owner}
    )
    assert _apply(db)["status"] == "APPLIED"

    db["ledger"][-1]["meta"]["actor_uid"] = other_owner
    db["credit_adjustment_audit"][0]["actor_uid"] = other_owner
    before = deepcopy(db)

    with pytest.raises(ValueError, match="REVERSAL_IDEMPOTENCY_CONFLICT"):
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



def test_concurrent_reversal_attempts_apply_compensation_once(monkeypatch, tmp_path):
    """Two simultaneous confirms use real atomic DB persistence and append one debit."""
    db = _db()
    _patch_runtime(monkeypatch, db)

    # Use the real state_manager atomic_update and file lock against an isolated
    # temporary DB. RPC and chain evidence remain mocked by _patch_runtime.
    import state_manager

    db_path = tmp_path / "db.json"
    monkeypatch.setattr(state_manager, "DB_FILE", str(db_path))
    monkeypatch.setattr(state_manager, "_LOCK_PATH", str(db_path) + ".lock")
    monkeypatch.setattr(state_manager, "_ensure_backup_scheduler", lambda: None)
    state_manager.save_db(db)
    real_load_db = state_manager.load_db
    real_atomic_update = state_manager.atomic_update
    monkeypatch.setattr(state_manager, "load_db", real_load_db)
    monkeypatch.setattr(state_manager, "atomic_update", real_atomic_update)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_apply, db), pool.submit(_apply, db)]
        results = [future.result() for future in futures]

    persisted = state_manager.load_db()
    statuses = [result["status"] for result in results]
    assert statuses.count("APPLIED") == 1
    assert statuses.count("ALREADY_REVERSED") == 1
    assert persisted["users"][UID]["wallet"]["credits"] == 20.072775
    corrections = [
        row for row in persisted["ledger"]
        if isinstance(row, dict)
        and isinstance(row.get("meta"), dict)
        and row["meta"].get("idempotency_key") == CORRECTION_KEY
    ]
    audit_rows = [
        row for row in persisted["credit_adjustment_audit"]
        if isinstance(row, dict)
        and row.get("correction_idempotency_key") == CORRECTION_KEY
    ]
    assert len(corrections) == 1
    assert len(audit_rows) == 1
