from pathlib import Path
import json
import hashlib

from core.mission_lifecycle import (
    MissionLifecycleService
)


BOARD_PATH = Path(
    "state/missions/board.json"
)


def load_board():

    return json.loads(
        BOARD_PATH.read_text(
            encoding="utf-8"
        )
    )


def find_mission(
    board,
    mission_id
):

    for mission in board.get(
        "missions",
        []
    ):

        if str(
            mission.get("id")
        ) == str(mission_id):

            return mission

    return None


def verify_result_hash(
    result
):

    stored = result.get(
        "result_sha256"
    )

    if not stored:

        return False

    payload = dict(
        result
    )

    payload.pop(
        "result_sha256",
        None
    )

    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False
    )

    calculated = hashlib.sha256(
        canonical.encode(
            "utf-8"
        )
    ).hexdigest()

    return calculated == stored


def main():

    print("=" * 80)
    print("       SLH MISSION #3 COMPLETION COMMIT")
    print("              CONTROLLED WRITE")
    print("=" * 80)

    mission_id = "3"

    service = MissionLifecycleService(".")

    board_before = load_board()

    mission_before = find_mission(
        board_before,
        mission_id
    )

    print()
    print("[PRE-COMMIT STATE]")

    if mission_before is None:

        print(
            "❌ MISSION #3 NOT FOUND"
        )

        return 1

    print(
        "Mission:",
        mission_before.get("id")
    )

    print(
        "Description:",
        mission_before.get("desc")
    )

    print(
        "Status:",
        mission_before.get("status")
    )

    print(
        "Assigned To:",
        mission_before.get("assigned_to")
    )

    pre_checks = [

        (
            "mission status == executed",
            mission_before.get(
                "status"
            )
            == "executed"
        ),

    ]

    for name, passed in pre_checks:

        print(
            "✅" if passed else "❌",
            name
        )

        if not passed:

            print(
                "❌ PRE-COMMIT STATE INVALID"
            )

            return 1

    print()
    print("[FINAL COMPLETION PREVIEW]")

    preview = service.preview_completion(
        mission_id=mission_id
    )

    print(
        "Status:",
        preview.get("status")
    )

    print(
        "Mission ID:",
        preview.get("mission_id")
    )

    print(
        "Current Status:",
        preview.get(
            "current_status"
        )
    )

    print(
        "Proposed Status:",
        preview.get(
            "proposed_status"
        )
    )

    print(
        "Proposed Completion:",
        preview.get(
            "proposed_completion"
        )
    )

    for name, passed in preview.get(
        "checks",
        {}
    ).items():

        print(
            "✅" if passed else "❌",
            name
        )

        if not passed:

            print(
                "❌ COMPLETION PREVIEW BLOCKED"
            )

            return 1

    preview_checks = [

        (
            "preview status == ready",
            preview.get(
                "status"
            )
            == "ready"
        ),

        (
            "preview write_performed == False",
            preview.get(
                "write_performed"
            )
            is False
        ),

        (
            "preview read_only == True",
            preview.get(
                "read_only"
            )
            is True
        ),

        (
            "proposed_status == completed",
            preview.get(
                "proposed_status"
            )
            == "completed"
        ),

    ]

    for name, passed in preview_checks:

        print(
            "✅" if passed else "❌",
            name
        )

        if not passed:

            print(
                "❌ PREVIEW SAFETY FAILURE"
            )

            return 1

    print()
    print(
        "✅ FINAL COMPLETION PREVIEW PASSED"
    )

    print()
    print(
        "[CONTROLLED API COMPLETION]"
    )

    result = service.complete_mission(
        mission_id=mission_id
    )

    print(
        "Status:",
        result.get("status")
    )

    print(
        "Mission ID:",
        result.get("mission_id")
    )

    print(
        "Agent ID:",
        result.get("agent_id")
    )

    print(
        "Mission Status:",
        result.get(
            "mission_status"
        )
    )

    print(
        "Mission Completion:",
        result.get(
            "mission_completion"
        )
    )

    print(
        "Completed At:",
        result.get(
            "completed_at"
        )
    )

    print(
        "Result Path:",
        result.get(
            "result_path"
        )
    )

    print(
        "Backup:",
        result.get(
            "backup"
        )
    )

    print(
        "Write Performed:",
        result.get(
            "write_performed"
        )
    )

    print()
    print(
        "[POST-COMPLETION VERIFICATION]"
    )

    board_after = load_board()

    mission_after = find_mission(
        board_after,
        mission_id
    )

    result_path = Path(
        result.get(
            "result_path"
        )
    )

    result_data = None

    if result_path.exists():

        result_data = json.loads(
            result_path.read_text(
                encoding="utf-8"
            )
        )

    checks = [

        (
            "API status == completed",
            result.get(
                "status"
            )
            == "completed"
        ),

        (
            "mission status == completed",
            mission_after is not None
            and mission_after.get(
                "status"
            )
            == "completed"
        ),

        (
            "completed_at exists",
            mission_after is not None
            and bool(
                mission_after.get(
                    "completed_at"
                )
            )
        ),

        (
            "mission_completion == completed",
            result_data is not None
            and result_data.get(
                "mission_completion"
            )
            == "completed"
        ),

        (
            "result completed_at exists",
            result_data is not None
            and bool(
                result_data.get(
                    "completed_at"
                )
            )
        ),

        (
            "result hash valid",
            result_data is not None
            and verify_result_hash(
                result_data
            )
        ),

        (
            "result file exists",
            result_path.exists()
        ),

        (
            "backup exists",
            result.get(
                "backup"
            )
            and Path(
                result.get(
                    "backup"
                )
            ).exists()
        ),

        (
            "write_performed == True",
            result.get(
                "write_performed"
            )
            is True
        ),

        (
            "read_only == False",
            result.get(
                "read_only"
            )
            is False
        ),

    ]

    failed = False

    for name, passed in checks:

        if passed:

            print(
                "✅",
                name
            )

        else:

            print(
                "❌",
                name
            )

            failed = True

    print()

    if failed:

        print(
            "❌ MISSION #3 COMPLETION COMMIT FAILED"
        )

        return 1

    print(
        "✅ MISSION #3 COMPLETION COMMIT PASSED"
    )

    print()
    print(
        "MISSION #3 IS NOW COMPLETED"
    )

    print(
        "EXECUTION RESULT UPDATED"
    )

    print(
        "RESULT HASH RECOMPUTED AND VERIFIED"
    )

    print(
        "BACKUP VERIFIED"
    )

    print()
    print(
        "STATUS: FULL MISSION LIFECYCLE VERIFIED"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
