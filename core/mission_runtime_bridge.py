from core.mission_lifecycle import MissionLifecycleService
from core.kernel import SLHKernel
from core.runtime import Runtime
from core.agent_factory import load_agents_into_kernel
from core.mission_state import MissionStateNormalizer


def execute_mission_via_runtime(mission_id, root=".", runtime=None, kernel=None):
    if kernel is None:
        kernel = SLHKernel()
        load_agents_into_kernel(kernel)

    if runtime is None:
        runtime = Runtime(kernel)

    lifecycle = MissionLifecycleService(root)
    board, manifest = lifecycle.load_state()
    mission = lifecycle.find_mission(board, mission_id)

    if mission is None:
        return {"status": "missing", "mission_id": str(mission_id)}

    status = MissionStateNormalizer.normalize(mission.get("status"))
    assigned_agent = mission.get("assigned_to")

    if status == "open":
        return {
            "status": "blocked",
            "mission_id": str(mission_id),
            "reason": "mission is open, assign an agent first",
        }

    if status == "assigned":
        lifecycle.execute_mission(mission_id=mission_id)

    if status not in ("assigned", "executed"):
        return {
            "status": "blocked",
            "mission_id": str(mission_id),
            "reason": f"mission status is {status}, cannot execute",
        }

    if not assigned_agent:
        return {
            "status": "blocked",
            "mission_id": str(mission_id),
            "reason": "no assigned_agent",
        }

    event = {
        "cmd": f"{assigned_agent}:execute_mission",
        "mission_id": str(mission_id),
        "source": "mission_runtime_bridge",
    }

    execution_result = runtime.execute(event)

    if isinstance(execution_result, dict) and execution_result.get("type") == "agent":
        lifecycle.complete_mission(mission_id=mission_id)
        lifecycle_result = {
            "status": "completed",
            "mission_id": str(mission_id),
        }
    else:
        lifecycle_result = {
            "status": "execution_failed",
            "mission_id": str(mission_id),
        }

    return {
        "mission_id": str(mission_id),
        "assigned_agent": assigned_agent,
        "execution_result": execution_result,
        "lifecycle_result": lifecycle_result,
    }
