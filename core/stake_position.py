"""
SLH Stake Position v1
Source of truth: state/db.json -> stake_positions
"""
import json, time
from pathlib import Path

DB = Path("state/db.json")


def _load():
    return json.loads(DB.read_text(encoding="utf-8"))


def _save(db):
    import os
    os.makedirs(DB.parent, exist_ok=True)
    DB.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def create_position(uid, amount, lock_days=30):
    if amount <= 0:
        raise ValueError("amount must be positive")

    db = _load()
    pos = {
        "id": f"sp_{int(time.time()*1000)}",
        "uid": str(uid),
        "amount": float(amount),
        "lock_days": int(lock_days),
        "created_at": time.time(),
        "unlocks_at": time.time() + int(lock_days) * 86400,
        "status": "locked",
    }

    db.setdefault("stake_positions", {})[pos["id"]] = pos
    _save(db)
    return pos


def get_positions(uid=None):
    db = _load()
    positions = db.get("stake_positions", {})
    if uid is None:
        return positions
    return {
        k: v for k, v in positions.items()
        if str(v.get("uid")) == str(uid)
    }


def get_position(position_id):
    return _load().get("stake_positions", {}).get(position_id)


def unlock_position(position_id):
    db = _load()
    pos = db.get("stake_positions", {}).get(position_id)
    if not pos:
        raise KeyError("position not found")
    if pos.get("status") == "unlocked":
        return pos

    if time.time() < float(pos.get("unlocks_at", 0)):
        raise ValueError("still locked")

    pos["status"] = "unlocked"
    pos["unlocked_at"] = time.time()
    _save(db)
    return pos
