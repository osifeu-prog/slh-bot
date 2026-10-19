from copy import deepcopy
from datetime import datetime, timezone

from core import staking_service
from core.account_ledger_audit import audit_account_ledger


UID = "8789977826"
POSITION_ID = "sp_1000004"


def _iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def _base_db(legacy_row=None, status="locked", unlocked_at=None, amount=100.0):
    position = {
        "id": POSITION_ID,
        "uid": UID,
        "amount": amount,
        "lock_days": 30,
        "created_at": 1000.0,
        "unlocks_at": 0,
        "status": status,
    }
    if unlocked_at is not None:
        position["unlocked_at"] = unlocked_at
    return {
        "users": {UID: {"wallet": {"credits": 500.0, "staked": 300.0}}},
        "stake_positions": {POSITION_ID: position},
        "ledger": [deepcopy(legacy_row)] if legacy_row else [],
        "staking_unstake_requests": {},
    }


def _legacy_unstake(amount=100.0, at=1049.0, position_id=None):
    meta = {"source": "telegram", "command": "unstake"}
    if position_id:
        meta["position_id"] = position_id
    return {
        "time": _iso(at),
        "uid": UID,
        "before": 400.0,
        "amount": amount,
        "after": 400.0 + amount,
        "reason": "staking:unstake",
        "meta": meta,
    }


def _patch_atomic_db(monkeypatch, db):
    monkeypatch.setattr(
        staking_service.state_manager,
        "atomic_update",
        lambda mutator: mutator(db),
    )


def test_legacy_unstake_amount_then_new_unstake_by_id_blocks_without_mutation(monkeypatch):
    db = _base_db(legacy_row=_legacy_unstake(amount=100.0, at=1049.0))
    before = deepcopy(db)
    _patch_atomic_db(monkeypatch, db)
    monkeypatch.setattr(staking_service.time, "time", lambda: 2000.0)

    result = staking_service.unstake_locked(UID, POSITION_ID)

    assert result["status"] == "legacy_refund_review_required"
    assert result["code"] == "LEGACY_UNSTAKE_AMBIGUITY"
    assert result["evidence"]["ledger_index"] == 0
    assert result["evidence"]["seconds_from_creation"] == 49.0
    assert db == before


def test_larger_aggregate_refund_near_creation_is_not_false_matched(monkeypatch):
    db = _base_db(legacy_row=_legacy_unstake(amount=166.0, at=1049.0))
    _patch_atomic_db(monkeypatch, db)
    monkeypatch.setattr(staking_service.time, "time", lambda: 2000.0)

    result = staking_service.unstake_locked(UID, POSITION_ID)

    assert result["status"] == "completed"
    assert result["credits"] == 600.0
    assert result["staked"] == 200.0
    assert db["ledger"][-1]["meta"]["idempotency_key"] == f"unstake:{POSITION_ID}"


def test_same_amount_legacy_unstake_days_later_is_not_false_matched(monkeypatch):
    db = _base_db(legacy_row=_legacy_unstake(amount=100.0, at=1400.0))
    _patch_atomic_db(monkeypatch, db)
    monkeypatch.setattr(staking_service.time, "time", lambda: 2000.0)

    result = staking_service.unstake_locked(UID, POSITION_ID)

    assert result["status"] == "completed"
    assert db["stake_positions"][POSITION_ID]["status"] == "unlocked"


def test_position_linked_unstake_is_not_legacy_ambiguity(monkeypatch):
    db = _base_db(legacy_row=_legacy_unstake(
        amount=100.0, at=1049.0, position_id=POSITION_ID
    ))
    _patch_atomic_db(monkeypatch, db)
    monkeypatch.setattr(staking_service.time, "time", lambda: 2000.0)

    result = staking_service.unstake_locked(UID, POSITION_ID)

    assert result["status"] == "completed"
    assert db["ledger"][-1]["meta"]["idempotency_key"] == f"unstake:{POSITION_ID}"


def test_double_unstake_by_id_is_idempotent(monkeypatch):
    db = _base_db()
    _patch_atomic_db(monkeypatch, db)
    monkeypatch.setattr(staking_service.time, "time", lambda: 2000.0)

    first = staking_service.unstake_locked(UID, POSITION_ID)
    after_first = deepcopy(db)
    second = staking_service.unstake_locked(UID, POSITION_ID)

    assert first["status"] == "completed"
    assert second["status"] == "already_unlocked"
    assert db == after_first
    assert db["users"][UID]["wallet"]["credits"] == 600.0
    assert db["users"][UID]["wallet"]["staked"] == 200.0
    assert len(db["ledger"]) == 1
    assert db["ledger"][0]["meta"]["idempotency_key"] == f"unstake:{POSITION_ID}"


def test_locked_position_with_unlocked_at_fails_closed(monkeypatch):
    db = _base_db(unlocked_at=1500.0)
    before = deepcopy(db)
    _patch_atomic_db(monkeypatch, db)
    monkeypatch.setattr(staking_service.time, "time", lambda: 2000.0)

    result = staking_service.unstake_locked(UID, POSITION_ID)

    assert result["status"] == "already_unlocked"
    assert db == before


def test_gap_audit_still_blocks_two_unresolved_discontinuities():
    db = {
        "users": {UID: {"wallet": {"credits": 70.0}}},
        "ledger": [
            {"uid": UID, "before": 100.0, "amount": -10.0, "after": 90.0,
             "reason": "store:purchase"},
            {"uid": UID, "before": 50.0, "amount": -5.0, "after": 45.0,
             "reason": "store:purchase"},
            {"uid": UID, "before": 80.0, "amount": -10.0, "after": 70.0,
             "reason": "store:purchase"},
        ],
    }
    before = deepcopy(db)

    audit = audit_account_ledger(db, UID)

    assert audit["status"] == "BLOCKED"
    assert audit["continuity_break_count"] == 2
    assert "ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY" in audit["blockers"]
    assert db == before
