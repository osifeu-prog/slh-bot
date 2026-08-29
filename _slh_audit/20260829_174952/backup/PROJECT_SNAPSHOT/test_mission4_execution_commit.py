from pathlib import Path
import json

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


def main():

    print("=" * 80)
    print("       SLH MISSION #4 EXECUTION COMMIT")
    print("              CONTROLLED WRITE")
    print("=" * 80)

    mission_id = "4"

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
            "❌ MISSION #4 NOT FOUND"
        )

        return 1

    print(
        "Mission:",
        mission_before.get("id")
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

    for name, passed in (
        preview.get(
            "checks",
            {}
        )
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

    safety_checks = [

        (
            "preview status == ready",
            preview.get(
                "status"
            )
            == "ready"
        ),

        (
            "current status == assigned",
            preview.get(
                "current_status"
            )
            == "assigned"
        ),

        (
            "proposed status == executed",
            preview.get(
                "proposed_status"
            )
            == "executed"
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

    for name, passed in safety_checks:

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
        "Mission Status:",
        result.get(
            "mission_status"
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

    checks = [

        (
            "API status == executed",
            result.get(
                "status"
            )
            == "executed"
        ),

        (
            "mission exists",
            mission_after is not None
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
            "assigned_to preserved",
            mission_after is not None
            and str(
                mission_after.get(
                    "assigned_to"
                )
            )
            == "3"
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
            "write_performed == True",
            result.get(
                "write_performed"
            )
            is True
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
            "❌ MISSION #4 EXECUTION COMMIT FAILED"
        )

        return 1

    print(
        "✅ MISSION #4 EXECUTION COMMIT PASSED"
    )

    print()
    print(
        "MISSION #4 EXECUTED"
    )

    print(
        "STATUS: EXECUTED"
    )

    print(
        "NEXT: COMPLETION PREVIEW"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
