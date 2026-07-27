from core.mission_lifecycle import (
    MissionLifecycleService
)


def main():

    print("=" * 80)
    print("       SLH MISSION #4 EXECUTION PREVIEW")
    print("              READ-ONLY TEST")
    print("=" * 80)

    mission_id = "4"

    service = MissionLifecycleService(".")

    preview = service.preview_execution(
        mission_id=mission_id
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
        "Current Status:",
        preview.get(
            "current_status"
        )
    )

    print(
        "Assigned To:",
        preview.get(
            "assigned_to"
        )
    )

    print(
        "Proposed Status:",
        preview.get(
            "proposed_status"
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
            "current_status == assigned",
            preview.get(
                "current_status"
            )
            == "assigned"
        ),

        (
            "proposed_status == executed",
            preview.get(
                "proposed_status"
            )
            == "executed"
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
            "❌ MISSION #4 EXECUTION PREVIEW FAILED"
        )

        return 1

    print(
        "✅ MISSION #4 EXECUTION PREVIEW PASSED"
    )

    print()
    print(
        "MISSION #4 IS READY FOR CONTROLLED EXECUTION"
    )

    print(
        "NEXT: EXECUTE MISSION #4"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
