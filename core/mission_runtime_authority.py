"""Canonical bounded Mission Runtime authority.

The authority resolves the assigned runtime agent, sends a structured
allow-listed action contract through the canonical Runtime Service, verifies
the returned evidence, and only then commits the lifecycle execution state.
"""

import state_manager

from core import runtime_service
from core.mission_lifecycle import MissionLifecycleService
from core.mission_state import MissionStateNormalizer


def _resolve_agent(lifecycle, mission):
    assigned_id = mission.get("assigned_to")
    if assigned_id is None:
        return None

    try:
        agents = state_manager.get_agents()
        record = agents.get(str(assigned_id))
        if isinstance(record, dict):
            return record
    except Exception:
        pass

    board, manifest = lifecycle.load_state()
    return lifecycle.find_agent(manifest, assigned_id)


def execute_mission_authority(mission_id, root=".", runtime=None):
    lifecycle = MissionLifecycleService(root)
    board, _manifest = lifecycle.load_state()
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

    action_type = mission.get("action_type")
    action_payload = mission.get("action_payload")
    idempotency_key = mission.get("idempotency_key")
    if not action_type or not isinstance(action_payload, dict) or not idempotency_key:
        return {"status": "blocked", "mission_id": str(mission_id), "reason": "mission_execution_contract_missing"}

    agent = _resolve_agent(lifecycle, mission)
    if agent is None or not agent.get("runtime_class"):
        return {"status": "blocked", "mission_id": str(mission_id), "reason": "assigned_agent_not_runtime_eligible"}

    owner_id = agent.get("owner_id")
    if owner_id is None:
        return {"status": "blocked", "mission_id": str(mission_id), "reason": "trusted_owner_not_found"}

    event = {
        "cmd": f"{agent.get('name') or str(mission.get('assigned_to'))}:execute_mission",
        "mission_id": str(mission_id),
        "source": "mission_runtime_authority",
        "capability": "mission_execution",
        "action": "execute_mission",
        "action_type": str(action_type),
        "action_payload": dict(action_payload),
        "idempotency_key": str(idempotency_key),
        "owner_id": str(owner_id),
    }

    try:
        if runtime is not None:
            runtime_result = runtime.execute(event)
        else:
            runtime_result = runtime_service.execute_agent_event(
                mission.get("assigned_to"), event
            )
    except Exception as exc:
        return {
            "status": "blocked",
            "mission_id": str(mission_id),
            "reason": "runtime_unavailable",
            "error": type(exc).__name__,
        }

    data = runtime_result.get("data") if isinstance(runtime_result, dict) else None
    verified = (
        isinstance(data, dict)
        and runtime_result.get("type") == "agent"
        and data.get("execution_status") == "success"
        and data.get("verified") is True
        and data.get("mission_id") == str(mission_id)
        and data.get("action_type") == str(action_type)
        and data.get("idempotency_key") == str(idempotency_key)
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

    lifecycle_result = lifecycle.execute_mission(
        mission_id=str(mission_id),
        execution_result=data,
    )
    if lifecycle_result.get("status") != "executed":
        return {
            "status": "blocked",
            "mission_id": str(mission_id),
            "reason": "lifecycle_execution_commit_failed",
            "lifecycle_result": lifecycle_result,
        }

    return {
        "status": "executed",
        "mission_id": str(mission_id),
        "agent_id": str(mission.get("assigned_to")),
        "runtime_result": runtime_result,
        "lifecycle_result": lifecycle_result,
    }
