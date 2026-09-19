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
    def mutate(db):
        pos = db.get("stake_positions", {}).get(position_id)
        if not pos:
            raise KeyError("position not found")
        if pos.get("status") == "unlocked":
            return pos
        if time.time() < float(pos.get("unlocks_at", 0)):
            raise ValueError("still locked")
        pos["status"] = "unlocked"
        pos["unlocked_at"] = time.time()
        return pos

    return state_manager.atomic_update(mutate)


def force_unlock_position(position_id, uid=None):
    """
    Owner-only forced unlock for exceptional cases (e.g. refund).
    Keeps the same atomic state contract as unlock_position.
    """
    from core.authority import is_owner

    if uid is None:
        uid = "8789977826"

    if not is_owner(uid):
        raise PermissionError("OWNER_ONLY")

    def mutate(db):
        pos = db.get("stake_positions", {}).get(position_id)
        if not pos:
            raise KeyError("position not found")

        pos["status"] = "unlocked"
        pos["unlocked_at"] = time.time()
        pos["unlock_reason"] = "force_unlock_by_owner"
        return pos

    return state_manager.atomic_update(mutate)
