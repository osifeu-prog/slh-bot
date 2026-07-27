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
    print("       SLH MISSION #4 CREATION COMMIT")
    print("              CONTROLLED WRITE")
    print("=" * 80)

    mission_id = "4"

    description = (
        "API LIFECYCLE INTEGRATION TEST"
    )

    reward = 0

    service = MissionLifecycleService(".")

    board_before = load_board()

    existing = find_mission(
        board_before,
        mission_id
    )

    print()
    print("[PRE-COMMIT STATE]")

    print(
        "Mission Exists:",
        existing is not None
    )

    if existing is not None:

        print(
            "❌ MISSION #4 ALREADY EXISTS"
        )

        return 1

    print(
        "✅ MISSION #4 DOES NOT EXIST"
    )

    print()
    print("[FINAL CREATION PREVIEW]")

    preview = (
        service.preview_mission_creation(
            mission_id=mission_id,
            description=description,
            reward=reward
        )
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
        "Proposed Status:",
        preview.get(
            "proposed_status"
        )
    )

    print(
        "Proposed Creation:",
        preview.get(
            "proposed_creation"
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
                "❌ CREATION PREVIEW BLOCKED"
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
            "proposed_creation == create",
            preview.get(
                "proposed_creation"
            )
            == "create"
        ),

        (
            "proposed_status == open",
            preview.get(
                "proposed_status"
            )
            == "open"
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
        "✅ FINAL CREATION PREVIEW PASSED"
    )

    print()
    print(
        "[CONTROLLED API CREATION]"
    )

    result = service.create_mission(
        mission_id=mission_id,
        description=description,
        reward=reward
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
        "[POST-CREATION VERIFICATION]"
    )

    board_after = load_board()

    mission_after = find_mission(
        board_after,
        mission_id
    )

    checks = [

        (
            "API status == created",
            result.get(
                "status"
            )
            == "created"
        ),

        (
            "mission exists",
            mission_after is not None
        ),

        (
            "mission status == open",
            mission_after is not None
            and mission_after.get(
                "status"
            )
            == "open"
        ),

        (
            "mission description matches",
            mission_after is not None
            and mission_after.get(
                "desc"
            )
            == description
        ),

        (
            "mission reward == 0",
            mission_after is not None
            and mission_after.get(
                "reward"
            )
            == reward
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
            "❌ MISSION #4 CREATION COMMIT FAILED"
        )

        return 1

    print(
        "✅ MISSION #4 CREATION COMMIT PASSED"
    )

    print()
    print(
        "MISSION #4 CREATED"
    )

    print(
        "STATUS: OPEN"
    )

    print(
        "NEXT: ASSIGNMENT PREVIEW"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
