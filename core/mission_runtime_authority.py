"""Canonical mission execution authority.

Mission execution enters here, runs through the canonical Runtime allowlist,
persists only verified execution evidence, then completes and rewards the
mission.
"""

import state_manager

from core import runtime_service
from core.mission_lifecycle import MissionLifecycleService
from core.mission_state import MissionStateNormalizer
from core.mission_execution_persistence import persist_verified_execution
from core.mission_reward_service import issue_mission_reward


def _resolve_agent(assigned_agent_id, manifest, root):
    target_id = str(assigned_agent_id)
    try:
        db = state_manager.load_db()
        record = (db.get("agents", {}) or {}).get(target_id)
        if isinstance(record, dict):
            return record
    except Exception:
        pass
    return MissionLifecycleService(root).find_agent(manifest, target_id)


def execute_mission_authority(mission_id, root=".", runtime=None, kernel=None):
    lifecycle = MissionLifecycleService(root)
    board, manifest = lifecycle.load_state()
    mission = lifecycle.find_mission(board, mission_id)
    if mission is None:
        return {"status": "blocked", "mission_id": str(mission_id), "reason": "mission_not_found"}

    status = MissionStateNormalizer.normalize(mission.get("status"))
    if status != "assigned":
        return {
            "status": "blocked",
            "mission_id": str(mission_id),
            "reason": "mission_not_executable",
            "current_status": status,
        }

    if not mission.get("action_type") or not isinstance(mission.get("action_payload"), dict) or not mission.get("idempotency_key"):
        return {
            "status": "blocked",
            "mission_id": str(mission_id),
            "reason": "mission_execution_contract_missing",
        }

    assigned_id = mission.get("assigned_to")
    agent = _resolve_agent(assigned_id, manifest, root)
    if agent is None or not agent.get("runtime_class"):
        return {
            "status": "blocked",
            "mission_id": str(mission_id),
            "reason": "assigned_agent_not_runtime_eligible",
        }

    event = {
        "cmd": f"{agent.get('name') or str(assigned_id)}:execute_mission",
        "mission_id": str(mission_id),
        "source": "mission_runtime_authority",
    }

    if runtime is not None:
        runtime_result = runtime.execute(event)
    else:
        # The production/default path uses the already-booted canonical runtime.
        # kernel is retained only for test injection/backward compatibility.
        if kernel is not None:
            from core.runtime import Runtime
            runtime_result = Runtime(kernel).execute(event)
        else:
            runtime_result = runtime_service.execute_agent_event(assigned_id, event)

    data = runtime_result.get("data") if isinstance(runtime_result, dict) else None
    verified = (
        isinstance(data, dict)
        and runtime_result.get("type") == "agent"
        and data.get("execution_status") == "success"
        and data.get("verified") is True
        and data.get("mission_id") == str(mission_id)
        and data.get("action_type") == str(mission.get("action_type"))
        and data.get("idempotency_key") == str(mission.get("idempotency_key"))
        and isinstance(data.get("evidence"), dict)
        and bool(data.get("evidence"))
    )
    if not verified:
        return {
            "status": "blocked",
            "mission_id": str(mission_id),
            "reason": "runtime_result_not_verified",
            "runtime_result": runtime_result,
        }

    persistence = persist_verified_execution(mission_id, data, root=root)
    if persistence.get("status") != "executed":
        return {
            "status": "blocked",
            "mission_id": str(mission_id),
            "reason": "execution_persistence_failed",
            "persistence": persistence,
        }

    final_board, _ = lifecycle.load_state()
    final_mission = lifecycle.find_mission(final_board, mission_id)
    completion = lifecycle.complete_mission(mission_id=mission_id)
    if completion.get("status") == "completed":
        reward = issue_mission_reward(final_mission, mission_id=mission_id) if final_mission else {"status": "blocked", "reason": "MISSION_NOT_FOUND"}
    else:
        reward = {"status": "not_attempted", "reason": completion.get("reason", "completion_failed")}

    return {
        "status": "completed" if completion.get("status") == "completed" else "blocked",
        "mission_id": str(mission_id),
        "agent_id": str(assigned_id),
        "runtime_result": runtime_result,
        "persistence": persistence,
        "completion": completion,
        "reward": reward,
    }
