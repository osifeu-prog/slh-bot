class MissionExecutorAgent:
    """Bounded mission execution adapter.

    The agent never manufactures success. A real executor must supply
    an explicit, verified result with evidence.
    """

    def __init__(self, context=None):
        self.context = context or {}

    def process(self, event):
        cmd = event.get("cmd", "")

        if not (
            cmd.endswith(":execute_mission")
            or cmd == "execute_mission"
        ):
            return {
                "error": "unsupported_command",
                "cmd": cmd,
            }

        execution_result = event.get("execution_result")

        if not isinstance(execution_result, dict):
            return {
                "execution_status": "blocked",
                "reason": "execution_result_required",
                "mission_id": str(event.get("mission_id", "")),
            }

        if execution_result.get("execution_status") != "success":
            return {
                "execution_status": "blocked",
                "reason": "execution_not_successful",
                "mission_id": str(event.get("mission_id", "")),
            }

        if execution_result.get("verified") is not True:
            return {
                "execution_status": "blocked",
                "reason": "execution_not_verified",
                "mission_id": str(event.get("mission_id", "")),
            }

        if not execution_result.get("evidence"):
            return {
                "execution_status": "blocked",
                "reason": "execution_evidence_required",
                "mission_id": str(event.get("mission_id", "")),
            }

        result = dict(execution_result)
        result.setdefault(
            "mission_id",
            str(event.get("mission_id", "")),
        )
        result.setdefault(
            "source",
            event.get("source"),
        )
        result.setdefault(
            "mission_completion",
            "pending",
        )
        return result
