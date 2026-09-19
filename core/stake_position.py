"""
SLH Stake Position v1
Source of truth: state/db.json -> stake_positions
All mutations go through state_manager.atomic_update for lock-safe writes.
"""
import time
import state_manager


def create_position(uid, amount, lock_days=30):
    """DEPRECATED - unsafe. Created positions without updating wallet["staked"]
    or writing a ledger entry. Root cause of RECON-240-20260919.
    Use core.staking_service.stake_locked() instead."""
    raise RuntimeError(
        "create_position is deprecated and unsafe: it does not update "
        "wallet['staked'] or the ledger. Use staking_service.stake_locked()."
    )


def get_positions(uid=None):
    db = state_manager.load_db()
    positions = db.get("stake_positions", {})
    if uid is None:
        return positions
    return {
        k: v for k, v in positions.items()
        if str(v.get("uid")) == str(uid)
    }


def get_position(position_id):
    db = state_manager.load_db()
    return db.get("stake_positions", {}).get(position_id)


def unlock_position(position_id):
    """DEPRECATED - unsafe legacy unlock path.

    Do not use this function because it changes only the position and can
    desynchronise wallet/ledger state.
    Use core.staking_service.unstake_locked(uid, position_id) instead.
    """
    raise RuntimeError(
        "unlock_position is deprecated and unsafe: it does not update "
        "wallet['staked'], wallet['credits'], or the ledger. "
        "Use staking_service.unstake_locked()."
    )


def force_unlock_position(position_id, uid=None):
    """DEPRECATED - unsafe legacy forced-unlock path.

    Forced unlocks must have a dedicated atomic refund/unlock authority that
    updates the wallet, position and ledger together. This legacy function
    only changed the position and is therefore disabled.
    """
    raise RuntimeError(
        "force_unlock_position is deprecated and unsafe: use a dedicated "
        "atomic refund/unlock authority instead."
    )
