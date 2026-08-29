from core.mission_lifecycle import (
    MissionLifecycleService
)


def main():

    print("=" * 80)
    print("       SLH MISSION #3 ASSIGNMENT PREVIEW")
    print("              READ-ONLY TEST")
    print("=" * 80)

    mission_id = "3"
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

    print()
    print("[CHECKS]")

    failed = False

    for name, passed in preview.get(
        "checks",
        {}
    ).items():

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

    print(
        "Write Performed:",
        preview.get(
            "write_performed"
        )
    )

    print(
        "Read Only:",
        preview.get(
            "read_only"
        )
    )

    print()

    safety_checks = [

        (
            "status == ready",
            preview.get(
                "status"
            )
            == "ready"
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

    ]

    print("[SAFETY ASSERTIONS]")

    for name, passed in safety_checks:

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
            "❌ MISSION #3 ASSIGNMENT PREVIEW FAILED"
        )

        return 1

    print(
        "✅ MISSION #3 ASSIGNMENT PREVIEW PASSED"
    )

    print()
    print(
        "MISSION #3 IS READY TO BE ASSIGNED"
    )

    print(
        "NEXT: CONTROLLED ASSIGNMENT COMMIT"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
