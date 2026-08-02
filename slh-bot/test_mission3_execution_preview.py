from core.mission_lifecycle import (
    MissionLifecycleService
)


def main():

    print("=" * 80)
    print("       SLH MISSION #3 EXECUTION PREVIEW")
    print("              READ-ONLY TEST")
    print("=" * 80)

    mission_id = "3"

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
        "Description:",
        preview.get("description")
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
        "Proposed Execution:",
        preview.get(
            "proposed_execution"
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
            "❌ MISSION #3 EXECUTION PREVIEW FAILED"
        )

        return 1

    print(
        "✅ MISSION #3 EXECUTION PREVIEW PASSED"
    )

    print()
    print(
        "MISSION #3 IS READY FOR CONTROLLED EXECUTION"
    )

    print(
        "NEXT: IMPLEMENT OR VALIDATE EXECUTION COMMIT API"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
