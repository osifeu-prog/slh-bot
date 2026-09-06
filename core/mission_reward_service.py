"""Mission reward authority.

Mission state and wallet state live in different stores, so completion and
payment cannot be a single filesystem transaction. This service makes reward
issuance retry-safe and refuses to guess a recipient.
"""

from datetime import datetime, timezone

import state_manager


def _resolve_recipient(db, mission):
    explicit = mission.get("reward_uid")
    if explicit is not None and str(explicit) in db.get("users", {}):
        return str(explicit)

    agent_id = mission.get("assigned_to")
    if not agent_id:
        return None

    agent = db.get("agents", {}).get(str(agent_id))
    if isinstance(agent, dict):
        owner_id = agent.get("owner_id")
        if owner_id is not None and str(owner_id) in db.get("users", {}):
            return str(owner_id)

    # Some deployments represent an agent itself as a wallet user.
    if str(agent_id) in db.get("users", {}):
        return str(agent_id)

    return None


def issue_mission_reward(mission_id):
    mission_id = str(mission_id)

    def mutate(db):
        missions = db.get("missions") or db.get("mission_board")
        # The authoritative mission board is separate from db.json in the
        # current lifecycle. Keep this function for deployments that mirror it
        # into db.json, but do not silently manufacture a mission here.
        if not missions:
            return {"status": "pending", "reason": "MISSION_BOARD_EXTERNAL"}

        mission = missions.get(mission_id) if isinstance(missions, dict) else None
        if mission is None:
            return {"status": "pending", "reason": "MISSION_NOT_IN_DB"}

        reward = float(mission.get("reward", 0) or 0)
        if reward <= 0:
            return {"status": "no_reward", "mission_id": mission_id}

        ledger = db.setdefault("ledger", [])
        key = f"mission:{mission_id}:reward"
        for entry in ledger:
            if entry.get("meta", {}).get("idempotency_key") == key:
                return {"status": "duplicate", "mission_id": mission_id}

        recipient = _resolve_recipient(db, mission)
        if recipient is None:
            return {
                "status": "blocked",
                "reason": "MISSION_REWARD_RECIPIENT_NOT_FOUND",
                "mission_id": mission_id,
            }

        user = db["users"][recipient]
        wallet = user.setdefault("wallet", {})
        before = float(wallet.get("credits", 0) or 0)
        after = before + reward
        wallet["credits"] = after

        now = datetime.now(timezone.utc).isoformat()
        ledger.append({
            "time": now,
            "uid": recipient,
            "before": before,
            "amount": reward,
            "after": after,
            "reason": "mission:completion_reward",
            "meta": {
                "idempotency_key": key,
                "mission_id": mission_id,
                "agent_id": str(mission.get("assigned_to")),
            },
        })

        return {
            "status": "paid",
            "mission_id": mission_id,
            "uid": recipient,
            "reward": reward,
            "credits": after,
        }

    return state_manager.atomic_update(mutate)
