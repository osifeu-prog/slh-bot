import state_manager

from core.mission_action_registry import build_default_registry
from core.mission_action_adapters import execute_academy_complete_stage


class MissionExecutorAgent:
    def __init__(self, context=None):
        self.context = context or {}
        self.registry = build_default_registry()
        self.registry.register(
            "academy.complete_stage",
            execute_academy_complete_stage,
        )

    def _load_mission(self, mission_id):
        import json

        with open("state/missions/board.json", encoding="utf-8") as f:
            board = json.load(f)
        for mission in board.get("missions", []):
            if str(mission.get("id")) == str(mission_id):
                return mission
        return None

    def _resolve_owner(self, assigned_to):
        agents = state_manager.get_agents()
        record = agents.get(str(assigned_to))
        if not isinstance(record, dict):
            return None
        return record.get("owner_id")

    def process(self, event):
        cmd = event.get("cmd", "")
        if not (cmd.endswith(":execute_mission") or cmd == "execute_mission"):
            return {"error": "unsupported_command", "cmd": cmd}

        mission_id = str(event.get("mission_id", ""))
        if not mission_id:
            return {"execution_status": "blocked", "error": "missing_mission_id"}

        mission = self._load_mission(mission_id)
        if not mission:
            return {
                "execution_status": "blocked",
                "mission_id": mission_id,
                "verified": False,
                "error": "mission_not_found",
            }

        action_type = mission.get("action_type")
        payload = mission.get("action_payload")
        idempotency_key = mission.get("idempotency_key")

        if not action_type or not isinstance(payload, dict) or not idempotency_key:
            return {
                "execution_status": "blocked",
                "mission_id": mission_id,
                "verified": False,
                "error": "mission_execution_contract_missing",
            }

        owner_id = self._resolve_owner(mission.get("assigned_to"))
        if owner_id is None:
            return {
                "execution_status": "blocked",
                "mission_id": mission_id,
                "verified": False,
                "error": "trusted_owner_not_found",
            }

        result = self.registry.execute(
            action_type,
            mission_id=mission_id,
            payload=payload,
            context={"owner_id": str(owner_id)},
            idempotency_key=str(idempotency_key),
        )
        data = result.as_dict()
        data["execution_status"] = data["status"]
        data["mission_completion"] = "pending"
        data["source"] = event.get("source")
        return data
