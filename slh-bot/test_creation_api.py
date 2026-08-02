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
    print("       SLH MISSION CREATION API TEST")
    print("              MISSION #3")
    print("=" * 80)

    mission_id = "3"

    description = (
        "API LIFECYCLE TEST"
    )

    reward = 0

    service = MissionLifecycleService(".")

    board_before = load_board()

    existing = find_mission(
        board_before,
        mission_id
    )

    print()
    print("[PRE-CREATION CHECK]")

    if existing is not None:

        print(
            "❌ Mission #3 already exists"
        )

        print(
            "Status:",
            existing.get("status")
        )

        return 1

    print(
        "✅ Mission #3 does not exist"
    )

    print()
    print("[CONTROLLED API CREATION]")

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
        "Description:",
        result.get("description")
    )

    print(
        "Mission Status:",
        result.get("mission_status")
    )

    print(
        "Assigned To:",
        result.get("assigned_to")
    )

    print(
        "Created At:",
        result.get("created_at")
    )

    print(
        "Backup:",
        result.get("backup")
    )

    print(
        "Write Performed:",
        result.get("write_performed")
    )

    print()
    print("[POST-CREATION VERIFICATION]")

    board_after = load_board()

    mission = find_mission(
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
            mission is not None
        ),

        (
            "mission status == open",
            mission is not None
            and mission.get(
                "status"
            )
            == "open"
        ),

        (
            "assigned_to == None",
            mission is not None
            and mission.get(
                "assigned_to"
            ) is None
        ),

        (
            "description matches",
            mission is not None
            and mission.get(
                "desc"
            )
            == description
        ),

        (
            "reward == 0",
            mission is not None
            and mission.get(
                "reward"
            )
            == reward
        ),

        (
            "created_at exists",
            mission is not None
            and bool(
                mission.get(
                    "created_at"
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

        (
            "read_only == False",
            result.get(
                "read_only"
            )
            is False
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
            "❌ CREATION API TEST FAILED"
        )

        return 1

    print(
        "✅ CREATION API TEST PASSED"
    )

    print()
    print(
        "MISSION #3 CREATED SUCCESSFULLY"
    )

    print(
        "STATUS: OPEN"
    )

    print(
        "ASSIGNED TO: NONE"
    )

    print(
        "BACKUP: VERIFIED"
    )

    print()
    print(
        "STATUS: READY FOR MISSION #3 ASSIGNMENT PREVIEW"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
