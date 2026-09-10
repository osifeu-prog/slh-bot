import state_manager

from core.mission_lifecycle import MissionLifecycleService
from core.kernel import SLHKernel
from core.runtime import Runtime
from core.agent_factory import load_agents_into_kernel
from core.mission_state import MissionStateNormalizer


def _resolve_assigned_agent(assigned_agent_id, manifest):
    """Prefer canonical DB identity; use the legacy manifest only as fallback."""
    target_id = str(assigned_agent_id)

    try:
        db = state_manager.load_db()
        record = (db.get("agents", {}) or {}).get(target_id)
        if isinstance(record, dict):
            return record
    except Exception:
        pass

    return MissionLifecycleService(".").find_agent(manifest, target_id)


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
    assigned_agent_id = mission.get("assigned_to")

    if status == "open":
        return {
            "status": "blocked",
            "mission_id": str(mission_id),
            "reason": "mission is open, assign an agent first",
        }

    if status not in ("assigned", "executed"):
        return {
            "status": "blocked",
            "mission_id": str(mission_id),
            "reason": f"mission status is {status}, cannot execute",
        }

    if not assigned_agent_id:
        return {
            "status": "blocked",
            "mission_id": str(mission_id),
            "reason": "no assigned_agent",
        }

    agent = _resolve_assigned_agent(assigned_agent_id, manifest)

    if agent is None:
        return {
            "status": "blocked",
            "mission_id": str(mission_id),
            "reason": "assigned agent not found in canonical DB or legacy manifest",
        }

    runtime_class = agent.get("runtime_class")
    if not runtime_class:
        return {
            "status": "blocked",
            "mission_id": str(mission_id),
            "assigned_agent_id": str(assigned_agent_id),
            "reason": "assigned agent has no runtime_class",
        }

    agent_name = agent.get("name") or str(assigned_agent_id)

    event = {
        "cmd": f"{agent_name}:execute_mission",
        "mission_id": str(mission_id),
        "source": "mission_runtime_bridge",
    }

    execution_result = runtime.execute(event)

    semantic_ok = (
        isinstance(execution_result, dict)
        and execution_result.get("type") == "agent"
        and execution_result.get("data")
        and isinstance(execution_result.get("data"), dict)
        and execution_result["data"].get("execution_status") == "success"
        and execution_result["data"].get("mission_id") == str(mission_id)
    )

    if semantic_ok:
        if status == "assigned":
            lifecycle.execute_mission(mission_id=mission_id)

        completion = lifecycle.complete_mission(
            mission_id=mission_id
        )

        lifecycle_result = {
            "status": completion.get("status"),
            "mission_id": str(mission_id),
            "completion": completion,
        }
    else:
        lifecycle_result = {
            "status": "execution_failed",
            "mission_id": str(mission_id),
            "reason": "runtime_execution_semantics_not_verified",
            "execution_result": execution_result,
        }

    return {
        "mission_id": str(mission_id),
        "assigned_agent": agent_name,
        "assigned_agent_id": assigned_agent_id,
        "runtime_class": runtime_class,
        "execution_result": execution_result,
        "lifecycle_result": lifecycle_result,
    }
