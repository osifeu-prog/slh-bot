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
    print("       SLH MISSION #3 ASSIGNMENT COMMIT")
    print("              CONTROLLED WRITE")
    print("=" * 80)

    mission_id = "3"
    agent_id = "3"

    service = MissionLifecycleService(".")

    board_before = load_board()

    mission_before = find_mission(
        board_before,
        mission_id
    )

    print()
    print("[PRE-COMMIT STATE]")

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

    if (
        mission_before.get("status")
        != "open"
    ):

        print(
            "❌ MISSION #3 IS NOT OPEN"
        )

        return 1

    if (
        mission_before.get("assigned_to")
        is not None
    ):

        print(
            "❌ MISSION #3 IS ALREADY ASSIGNED"
        )

        return 1

    print()
    print("[FINAL PREVIEW]")

    preview = service.preview_assignment(
        mission_id,
        agent_id
    )

    print(
        "Status:",
        preview.get("status")
    )

    for name, passed in preview.get(
        "checks",
        {}
    ).items():

        print(
            "✅" if passed else "❌",
            name
        )

    if preview.get(
        "status"
    ) != "ready":

        print(
            "❌ ASSIGNMENT PREVIEW BLOCKED"
        )

        return 1

    if preview.get(
        "write_performed"
    ) is not False:

        print(
            "❌ PREVIEW SAFETY FAILURE"
        )

        return 1

    print()
    print(
        "✅ FINAL PREVIEW PASSED"
    )

    print()
    print("[CONTROLLED API COMMIT]")

    result = service.assign_mission(
        mission_id,
        agent_id
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
        "Assigned At:",
        result.get("assigned_at")
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
    print("[POST-COMMIT VERIFICATION]")

    board_after = load_board()

    mission_after = find_mission(
        board_after,
        mission_id
    )

    checks = [

        (
            "commit status == assigned",
            result.get("status")
            == "assigned"
        ),

        (
            "mission exists",
            mission_after is not None
        ),

        (
            "mission status == assigned",
            mission_after is not None
            and mission_after.get(
                "status"
            )
            == "assigned"
        ),

        (
            "assigned_to == 3",
            mission_after is not None
            and str(
                mission_after.get(
                    "assigned_to"
                )
            )
            == "3"
        ),

        (
            "assigned_at exists",
            mission_after is not None
            and bool(
                mission_after.get(
                    "assigned_at"
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
            "❌ MISSION #3 ASSIGNMENT COMMIT FAILED"
        )

        return 1

    print(
        "✅ MISSION #3 ASSIGNMENT COMMIT PASSED"
    )

    print()
    print(
        "MISSION #3 IS NOW ASSIGNED TO AGENT 3"
    )

    print(
        "BACKUP VERIFIED"
    )

    print(
        "STATUS: READY FOR EXECUTION PREVIEW"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
