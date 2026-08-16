from core.mission_lifecycle import (
    MissionLifecycleService
)


def main():

    print("=" * 80)
    print("       SLH MISSION #4 ASSIGNMENT PREVIEW")
    print("              READ-ONLY TEST")
    print("=" * 80)

    mission_id = "4"
    agent_id = "3"

    service = MissionLifecycleService(".")

    preview = service.preview_assignment(
        mission_id=mission_id,
        agent_id=agent_id
    )

    print()
    print("[PREVIEW RESULT]")

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
        "Current Mission Status:",
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
        "Proposed Assigned To:",
        preview.get(
            "proposed_assigned_to"
        )
    )

    print()
    print("[CHECKS]")

    failed = False

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

            failed = True

    print()
    print("[SAFETY ASSERTIONS]")

    safety_checks = [

        (
            "status == ready",
            preview.get(
                "status"
            )
            == "ready"
        ),

        (
            "proposed_status == assigned",
            preview.get(
                "proposed_status"
            )
            == "assigned"
        ),

        (
            "proposed_assigned_to == 3",
            str(
                preview.get(
                    "proposed_assigned_to"
                )
            )
            == "3"
        ),

        (
            "write_performed == False",
            preview.get(
                "write_performed"
            )
            is False
        ),

        (
            "read_only == True",
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

            failed = True

    print()

    if failed:

        print(
            "❌ MISSION #4 ASSIGNMENT PREVIEW FAILED"
        )

        return 1

    print(
        "✅ MISSION #4 ASSIGNMENT PREVIEW PASSED"
    )

    print()
    print(
        "MISSION #4 IS READY FOR CONTROLLED ASSIGNMENT"
    )

    print(
        "NEXT: ASSIGN MISSION #4 TO AGENT #3"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
