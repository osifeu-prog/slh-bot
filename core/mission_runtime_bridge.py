from core.mission_lifecycle import MissionLifecycleService
from core.mission_reward_service import issue_mission_reward
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
    assigned_agent_id = mission.get("assigned_to")
    if status == "open":
        return {"status": "blocked", "mission_id": str(mission_id), "reason": "mission is open, assign an agent first"}
    if status not in ("assigned", "executed"):
        return {"status": "blocked", "mission_id": str(mission_id), "reason": f"mission status is {status}, cannot execute"}
    if not assigned_agent_id:
        return {"status": "blocked", "mission_id": str(mission_id), "reason": "no assigned_agent"}

    agent = lifecycle.find_agent(manifest, assigned_agent_id)
    if agent is None:
        return {"status": "blocked", "mission_id": str(mission_id), "reason": "assigned agent not found in manifest"}

    agent_name = agent.get("name") or str(assigned_agent_id)
    event = {"cmd": f"{agent_name}:execute_mission", "mission_id": str(mission_id), "source": "mission_runtime_bridge"}
    execution_result = runtime.execute(event)
    data = execution_result.get("data") if isinstance(execution_result, dict) else None
    semantic_ok = isinstance(data, dict) and execution_result.get("type") == "agent" and data.get("execution_status") == "success" and data.get("mission_id") == str(mission_id)

    if not semantic_ok:
        return {"mission_id": str(mission_id), "assigned_agent": agent_name, "assigned_agent_id": assigned_agent_id, "execution_result": execution_result, "lifecycle_result": {"status": "execution_failed", "reason": "runtime_execution_semantics_not_verified"}, "reward": {"status": "not_attempted"}}

    if status == "assigned":
        execution_state = lifecycle.execute_mission(mission_id=mission_id)
        if execution_state.get("status") != "executed":
            return {"mission_id": str(mission_id), "assigned_agent": agent_name, "assigned_agent_id": assigned_agent_id, "execution_result": execution_result, "lifecycle_result": execution_state, "reward": {"status": "not_attempted"}}

    completion = lifecycle.complete_mission(mission_id=mission_id)
    final_board, _ = lifecycle.load_state()
    final_mission = lifecycle.find_mission(final_board, mission_id)
    if completion.get("status") == "completed" or completion.get("reason") == "mission_already_completed":
        reward = issue_mission_reward(final_mission, mission_id=mission_id) if final_mission else {"status": "blocked", "reason": "MISSION_NOT_FOUND"}
    else:
        reward = {"status": "not_attempted", "reason": completion.get("reason", "completion_failed")}

    return {"mission_id": str(mission_id), "assigned_agent": agent_name, "assigned_agent_id": assigned_agent_id, "execution_result": execution_result, "lifecycle_result": {"status": completion.get("status"), "completion": completion}, "reward": reward}
