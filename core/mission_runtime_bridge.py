"""Compatibility facade for the canonical mission runtime authority."""

from core.mission_lifecycle import MissionLifecycleService
from core.mission_runtime_authority import execute_mission_authority
from core.mission_state import MissionStateNormalizer
from core.mission_reward_service import issue_mission_reward


def execute_mission_via_runtime(mission_id, root=".", runtime=None, kernel=None, *, requester_uid=None, requester_chat_id=None, human_approval_id=None):
    """Keep legacy callers on the canonical Mission Runtime authority.

    The bridge must not create a second Kernel/Runtime plane. Optional runtime
    injection is retained only for isolated tests and is passed to the authority.
    """
    lifecycle = MissionLifecycleService(root)
    board, _manifest = lifecycle.load_state()
    mission = lifecycle.find_mission(board, mission_id)
    if mission is None:
        return {"status": "missing", "mission_id": str(mission_id)}

    status = MissionStateNormalizer.normalize(mission.get("status"))
    execution = {"status": "already_executed"}
    if status == "assigned":
        execution = execute_mission_authority(
            mission_id=str(mission_id),
            root=root,
            runtime=runtime,
            requester_uid=requester_uid,
            requester_chat_id=requester_chat_id,
            human_approval_id=human_approval_id,
        )
        if execution.get("status") != "executed":
            return execution
    elif status != "executed":
        return {
            "status": "blocked",
            "mission_id": str(mission_id),
            "reason": "mission_not_executable",
            "current_status": status,
        }

    completion = lifecycle.complete_mission(
        mission_id=str(mission_id),
        requester_uid=requester_uid,
        requester_chat_id=requester_chat_id,
    )
    final_board, _manifest = lifecycle.load_state()
    final_mission = lifecycle.find_mission(final_board, mission_id)
    reward = {"status": "not_attempted"}
    if completion.get("status") == "completed" or completion.get("reason") == "mission_already_completed":
        if final_mission is not None:
            reward = issue_mission_reward(final_mission, mission_id=str(mission_id))

    status_out = (
        "completed" if completion.get("status") == "completed"
        else "approval_required" if completion.get("status") == "approval_required"
        else "blocked"
    )
    return {
        "status": status_out,
        "mission_id": str(mission_id),
        "execution_result": execution,
        "lifecycle_result": {"status": completion.get("status"), "completion": completion},
        "completion_request_id": completion.get("request_id"),
        "reward": reward,
    }
