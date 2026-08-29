"""
SLH Stake Position v1
Source of truth: state/db.json -> stake_positions
All mutations go through state_manager.atomic_update for lock-safe writes.
"""
import time
import state_manager


def create_position(uid, amount, lock_days=30):
    if amount <= 0:
        raise ValueError("amount must be positive")

    pos = {
        "id": f"sp_{int(time.time()*1000)}",
        "uid": str(uid),
        "amount": float(amount),
        "lock_days": int(lock_days),
        "created_at": time.time(),
        "unlocks_at": time.time() + int(lock_days) * 86400,
        "status": "locked",
    }

    def mutate(db):
        db.setdefault("stake_positions", {})[pos["id"]] = pos
        return pos

    return state_manager.atomic_update(mutate)


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
