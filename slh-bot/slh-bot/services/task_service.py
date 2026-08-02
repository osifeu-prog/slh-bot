from core.mission_lifecycle import MissionLifecycleService
import json, os
from datetime import datetime

BOARD_FILE = "state/missions/board.json"

def _load():
    if not os.path.exists(BOARD_FILE):
        return []
    with open(BOARD_FILE, "r") as f:
        data = json.load(f)
    return data.get("missions", [])

def _save(missions):
    os.makedirs(os.path.dirname(BOARD_FILE), exist_ok=True)
    board = {"missions": missions}
    with open(BOARD_FILE, "w") as f:
        json.dump(board, f, indent=2, ensure_ascii=False)

def list_tasks():
    """Read-only compatibility view owned by MissionLifecycleService."""

    from core.mission_lifecycle import (
        MissionLifecycleService
    )

    owner = MissionLifecycleService(
        "."
    )

    board, _manifest = owner.load_state()

    missions = board.get(
        "missions",
        []
    )

    result = []

    for mission in missions:

        status = owner.normalize_status(
            mission.get(
                "status"
            )
        )

        if status != "open":
            continue

        result.append(
            {
                "id": str(
                    mission.get(
                        "id"
                    )
                ),

                "desc": mission.get(
                    "desc",
                    ""
                ),

                "status": status,

                "assigned_to": mission.get(
                    "assigned_to"
                ),

                "reward": mission.get(
                    "reward",
                    0
                ),

                "created_at": mission.get(
                    "created_at",
                    mission.get(
                        "created"
                    )
                ),
            }
        )

    return result

def add_task(text):
    """
    Legacy-compatible adapter.

    Authoritative writer:
        MissionLifecycleService.create_mission()

    This function preserves the legacy return shape while ensuring
    that mission creation is owned by the lifecycle service.
    """

    from datetime import datetime, timezone

    mission_id = (
        "TASK-"
        + datetime.now(
            timezone.utc
        ).strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
    )

    owner = MissionLifecycleService(
        "."
    )

    result = owner.create_mission(
        mission_id=mission_id,
        description=text,
        reward=0
    )

    if result.get(
        "status"
    ) != "created":

        raise RuntimeError(
            "Mission creation blocked: "
            + repr(result)
        )

    return {
        "id": result.get(
            "mission_id"
        ),

        "desc": result.get(
            "description",
            text
        ),

        "status": result.get(
            "mission_status",
            "open"
        ),

        "assigned_to": result.get(
            "assigned_to"
        ),

        "reward": 0,

        "created": result.get(
            "created_at"
        ),

        "created_at": result.get(
            "created_at"
        ),
    }

def update_task_status(task_id, status):
    """
    Deprecated legacy status writer.

    Direct status mutation is disabled.

    Mission state must transition through:
        assign_mission()
        execute_mission()
        complete_mission()

    This function remains only as a compatibility surface so that
    accidental legacy callers fail explicitly instead of mutating
    mission state outside the authoritative lifecycle.
    """

    raise RuntimeError(
        "legacy_status_writer_disabled: "
        "use MissionLifecycleService lifecycle operations"
    )
