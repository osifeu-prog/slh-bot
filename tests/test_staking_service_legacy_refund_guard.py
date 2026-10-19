from copy import deepcopy
from datetime import datetime, timezone

from core import staking_service


UID = "8789977826"
POSITION_ID = "sp_1000004"


def _iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def _legacy_db(include_refund=True):
    position = {
        "id": POSITION_ID,
        "uid": UID,
        "amount": 100.0,
        "lock_days": 30,
        "created_at": 1000.004,
        "unlocks_at": 0,
        "status": "locked",
    }
    ledger = [{
        "time": _iso(1000.0),
        "uid": UID,
        "before": 500.0,
        "amount": -100.0,
        "after": 400.0,
        "reason": "staking:stake",
        "meta": {
            "source": "telegram",
            "command": "stake",
            "staked_before": 20.0,
            "staked_after": 120.0,
        },
    }]
    if include_refund:
        ledger.append({
            "time": _iso(1049.0),
            "uid": UID,
            "before": 400.0,
            "amount": 100.0,
            "after": 500.0,
            "reason": "staking:unstake",
            "meta": {
                "source": "telegram",
                "command": "unstake",
                "staked_before": 120.0,
                "staked_after": 20.0,
            },
        })
    return {
        "users": {UID: {"wallet": {"credits": 500.0, "staked": 300.0}}},
        "stake_positions": {POSITION_ID: position},
        "ledger": ledger,
    }


def _patch_atomic_db(monkeypatch, db):
    monkeypatch.setattr(
        staking_service.state_manager,
        "atomic_update",
        lambda mutator: mutator(db),
    )


def test_legacy_unstake_exact_inverse_blocks_second_refund_without_mutation(monkeypatch):
    db = _legacy_db(include_refund=True)
    before = deepcopy(db)
    _patch_atomic_db(monkeypatch, db)
    monkeypatch.setattr(staking_service.time, "time", lambda: 2000.0)

    result = staking_service.unstake_locked(UID, POSITION_ID)

    assert result["status"] == "legacy_refund_review_required"
    assert result["evidence"]["legacy_stake_index"] == 0
    assert result["evidence"]["legacy_unstake_index"] == 1
    assert db == before


def test_legacy_stake_without_prior_refund_can_follow_normal_unlock(monkeypatch):
    db = _legacy_db(include_refund=False)
    _patch_atomic_db(monkeypatch, db)
    monkeypatch.setattr(staking_service.time, "time", lambda: 2000.0)

    result = staking_service.unstake_locked(UID, POSITION_ID)

    assert result["status"] == "completed"
    assert result["credits"] == 600.0
    assert result["staked"] == 200.0
    assert db["stake_positions"][POSITION_ID]["status"] == "unlocked"
    assert db["ledger"][-1]["reason"] == "staking:unstake_locked"


def test_position_aware_new_stake_event_does_not_match_legacy_guard(monkeypatch):
    db = _legacy_db(include_refund=True)
    db["ledger"][0]["reason"] = "staking:stake_locked"
    db["ledger"][0]["meta"]["position_id"] = POSITION_ID
    _patch_atomic_db(monkeypatch, db)
    monkeypatch.setattr(staking_service.time, "time", lambda: 2000.0)

    result = staking_service.unstake_locked(UID, POSITION_ID)

    assert result["status"] == "completed"
    assert db["stake_positions"][POSITION_ID]["status"] == "unlocked"



def test_larger_legacy_aggregate_unstake_blocks_as_ambiguous(monkeypatch):
    db = _legacy_db(include_refund=False)
    # Later legacy command withdrew 166 Credits from aggregate staked funds.
    # With no position_id, allocation cannot be proven, but this 100-Credit
    # position could have been included in the aggregate refund.
    db["ledger"].append({
        "time": _iso(1200.0),
        "uid": UID,
        "before": 400.0,
        "amount": 166.0,
        "after": 566.0,
        "reason": "staking:unstake",
        "meta": {
            "source": "telegram",
            "command": "unstake",
            "staked_before": 166.0,
            "staked_after": 0.0,
        },
    })
    before = deepcopy(db)
    _patch_atomic_db(monkeypatch, db)
    monkeypatch.setattr(staking_service.time, "time", lambda: 2000.0)

    result = staking_service.unstake_locked(UID, POSITION_ID)

    assert result["status"] == "legacy_refund_review_required"
    assert result["evidence"]["classification"] == "LEGACY_AGGREGATE_UNSTAKE_POSSIBLY_INCLUDED_POSITION"
    assert result["evidence"]["legacy_unstake_amount"] == 166.0
    assert db == before
