from core.mission_action_adapters import execute_academy_complete_stage
from core.mission_action_registry import build_default_registry


class MissionExecutorAgent:
    """Bounded mission action adapter.

    Only explicitly registered action types can execute. The mission
    description is never interpreted as executable code.
    """

    def __init__(self, context=None):
        self.context = context or {}
        self.registry = build_default_registry()
        self.registry.register("academy.complete_stage", execute_academy_complete_stage)

    def process(self, event):
        cmd = event.get("cmd", "")
        if not (cmd.endswith(":execute_mission") or cmd == "execute_mission"):
            return {"error": "unsupported_command", "cmd": cmd}

        mission_id = str(event.get("mission_id", ""))
        capability = event.get("capability")
        action = event.get("action")
        action_type = event.get("action_type")
        action_payload = event.get("action_payload")
        idempotency_key = event.get("idempotency_key")
        owner_id = event.get("owner_id")

        if not mission_id:
            return {"execution_status": "blocked", "reason": "missing_mission_id"}
        if capability != "mission_execution" or action != "execute_mission":
            return {"execution_status": "blocked", "mission_id": mission_id, "reason": "unsupported_capability_or_action"}
        if not action_type or not isinstance(action_payload, dict) or not idempotency_key:
            return {"execution_status": "blocked", "mission_id": mission_id, "reason": "mission_execution_contract_missing"}
        if owner_id is None or str(owner_id).strip() == "":
            return {"execution_status": "blocked", "mission_id": mission_id, "reason": "trusted_owner_not_found"}

        result = self.registry.execute(
            action_type,
            mission_id=mission_id,
            payload=action_payload,
            context={"owner_id": str(owner_id)},
            idempotency_key=str(idempotency_key),
        )
        data = result.as_dict()
        data["execution_status"] = data["status"]
        data["mission_completion"] = "pending"
        data["source"] = event.get("source")
        return data
