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
    print("       SLH MISSION #4 ASSIGNMENT COMMIT")
    print("              CONTROLLED WRITE")
    print("=" * 80)

    mission_id = "4"
    agent_id = "3"

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
            "mission status == open",
            mission_before.get(
                "status"
            )
            == "open"
        ),

        (
            "mission is unassigned",
            mission_before.get(
                "assigned_to"
            )
            is None
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
    print("[FINAL ASSIGNMENT PREVIEW]")

    preview = service.preview_assignment(
        mission_id=mission_id,
        agent_id=agent_id
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
        "Proposed Status:",
        preview.get(
            "proposed_status"
        )
    )

    print(
        "Proposed Assigned To:",
        preview.get(
            "proposed_assigned_to"
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
                "❌ ASSIGNMENT PREVIEW BLOCKED"
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
            "proposed status == assigned",
            preview.get(
                "proposed_status"
            )
            == "assigned"
        ),

        (
            "proposed agent == 3",
            str(
                preview.get(
                    "proposed_assigned_to"
                )
            )
            == "3"
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
        "✅ FINAL ASSIGNMENT PREVIEW PASSED"
    )

    print()
    print(
        "[CONTROLLED API ASSIGNMENT]"
    )

    result = service.assign_mission(
        mission_id=mission_id,
        agent_id=agent_id
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
        "Assigned To:",
        result.get(
            "assigned_to"
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
        "[POST-ASSIGNMENT VERIFICATION]"
    )

    board_after = load_board()

    mission_after = find_mission(
        board_after,
        mission_id
    )

    checks = [

        (
            "API status == assigned",
            result.get(
                "status"
            )
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
            "❌ MISSION #4 ASSIGNMENT COMMIT FAILED"
        )

        return 1

    print(
        "✅ MISSION #4 ASSIGNMENT COMMIT PASSED"
    )

    print()
    print(
        "MISSION #4 ASSIGNED TO AGENT #3"
    )

    print(
        "STATUS: ASSIGNED"
    )

    print(
        "NEXT: EXECUTION PREVIEW"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
