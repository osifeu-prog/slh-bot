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
    print("       SLH MISSION #3 EXECUTION COMMIT")
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
            "mission status == assigned",
            mission_before.get(
                "status"
            )
            == "assigned"
        ),

        (
            "assigned_to == 3",
            str(
                mission_before.get(
                    "assigned_to"
                )
            )
            == "3"
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
    print("[FINAL EXECUTION PREVIEW]")

    preview = service.preview_execution(
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
        "Agent ID:",
        preview.get("agent_id")
    )

    print(
        "Proposed Execution:",
        preview.get(
            "proposed_execution"
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
                "❌ EXECUTION PREVIEW BLOCKED"
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
        "✅ FINAL EXECUTION PREVIEW PASSED"
    )

    print()
    print(
        "[CONTROLLED API EXECUTION]"
    )

    result = service.execute_mission(
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
        "Execution Status:",
        result.get(
            "execution_status"
        )
    )

    print(
        "Result ID:",
        result.get(
            "result_id"
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
        "[POST-EXECUTION VERIFICATION]"
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
            "API status == executed",
            result.get(
                "status"
            )
            == "executed"
        ),

        (
            "mission status == executed",
            mission_after is not None
            and mission_after.get(
                "status"
            )
            == "executed"
        ),

        (
            "execution_started_at exists",
            mission_after is not None
            and bool(
                mission_after.get(
                    "execution_started_at"
                )
            )
        ),

        (
            "execution_completed_at exists",
            mission_after is not None
            and bool(
                mission_after.get(
                    "execution_completed_at"
                )
            )
        ),

        (
            "execution_status == success",
            result_data is not None
            and result_data.get(
                "execution_status"
            )
            == "success"
        ),

        (
            "result verified == true",
            result_data is not None
            and result_data.get(
                "verified"
            )
            is True
        ),

        (
            "mission_completion == pending",
            result_data is not None
            and result_data.get(
                "mission_completion"
            )
            == "pending"
        ),

        (
            "synchronization check == passed",
            result_data is not None
            and result_data.get(
                "result",
                {}
            ).get(
                "synchronization_check"
            )
            == "passed"
        ),

        (
            "execution check == passed",
            result_data is not None
            and result_data.get(
                "result",
                {}
            ).get(
                "execution_check"
            )
            == "passed"
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
            "❌ MISSION #3 EXECUTION COMMIT FAILED"
        )

        return 1

    print(
        "✅ MISSION #3 EXECUTION COMMIT PASSED"
    )

    print()
    print(
        "MISSION #3 IS NOW EXECUTED"
    )

    print(
        "RESULT CREATED"
    )

    print(
        "RESULT HASH VERIFIED"
    )

    print(
        "BACKUP VERIFIED"
    )

    print()
    print(
        "STATUS: READY FOR COMPLETION PREVIEW"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
