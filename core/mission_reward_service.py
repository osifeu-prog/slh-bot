"""Retry-safe mission reward adapter."""

import state_manager
from core import economy_service


def _resolve_recipient(db, mission):
    users = db.get("users", {})
    agents = db.get("agents", {})

    explicit = mission.get("reward_uid")
    if explicit is not None and str(explicit) in users:
        return str(explicit)

    agent_id = mission.get("assigned_to")
    if not agent_id:
        return None

    agent = agents.get(str(agent_id))
    if not isinstance(agent, dict):
        manifest_path = "state/takeover/manifest.json"
        try:
            import json
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
            for candidate in manifest.get("agents", {}).get("items", []):
                if str(candidate.get("id")) == str(agent_id):
                    name = str(candidate.get("name", "")).strip().lower()
                    if name:
                        for canonical in agents.values():
                            if isinstance(canonical, dict) and str(canonical.get("name", "")).strip().lower() == name:
                                agent = canonical
                                break
                    break
        except Exception:
            agent = None

    if isinstance(agent, dict):
        owner_id = agent.get("owner_id")
        if owner_id is not None and str(owner_id) in users:
            return str(owner_id)

    if str(agent_id) in users:
        return str(agent_id)

    return None


def issue_mission_reward(mission, mission_id=None):
    if not isinstance(mission, dict):
        raise ValueError("INVALID_MISSION")

    mission_id = str(mission_id or mission.get("id") or "")
    if not mission_id:
        raise ValueError("INVALID_MISSION_ID")

    reward = float(mission.get("reward", 0) or 0)
    if reward < 0:
        raise ValueError("INVALID_MISSION_REWARD")
    if reward == 0:
        return {"status": "no_reward", "mission_id": mission_id}

    db = state_manager.load_db()
    recipient = _resolve_recipient(db, mission)
    if recipient is None:
        return {"status": "blocked", "reason": "MISSION_REWARD_RECIPIENT_NOT_FOUND", "mission_id": mission_id}

    key = f"mission:{mission_id}:reward"
    try:
        credits = economy_service.record_transaction(
            recipient,
            reward,
            reason="mission:completion_reward",
            meta={"idempotency_key": key, "mission_id": mission_id, "agent_id": str(mission.get("assigned_to"))},
        )
    except Exception as exc:
        return {"status": "blocked", "reason": "MISSION_REWARD_FAILED", "error": type(exc).__name__, "mission_id": mission_id, "uid": recipient}

    latest = state_manager.load_db()
    ledger = latest.get("ledger", [])
    paid = any(entry.get("meta", {}).get("idempotency_key") == key for entry in ledger)
    return {"status": "paid" if paid else "blocked", "mission_id": mission_id, "uid": recipient, "reward": reward if paid else 0, "credits": credits if paid else None}
