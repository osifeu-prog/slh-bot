"""
SLH Reward Engine v1 (design phase)
Source of truth: state/db.json -> reward_pools + stake_positions
"""
import json, time
from pathlib import Path

DB = Path("state/db.json")

def _load():
    return json.loads(DB.read_text(encoding="utf-8"))

def _save(db):
    DB.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

def calculate_reward(position_id, rate_per_day=0.0005):
    pos = _load().get("stake_positions", {}).get(position_id)
    if not pos:
        raise KeyError("position not found")
    days = max(0, (time.time() - pos.get("created_at", time.time())) / 86400)
    return round(float(pos["amount"]) * days * rate_per_day, 6)

def accrue(position_id):
    reward = calculate_reward(position_id)
    db = _load()
    pools = db.setdefault("reward_pools", {})
    pools[position_id] = {
        "position_id": position_id,
        "reward": reward,
        "calculated_at": time.time(),
        "status": "pending",
    }
    _save(db)
    return reward
