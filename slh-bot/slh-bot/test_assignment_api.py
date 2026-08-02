from core.mission_lifecycle import (
    MissionLifecycleService
)


def main():

    print("=" * 80)
    print("       SLH ASSIGNMENT API TEST")
    print("          NEGATIVE SAFETY TEST")
    print("=" * 80)

    service = MissionLifecycleService(".")

    preview = service.preview_assignment(
        mission_id="1",
        agent_id="3"
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
    print("[EXPECTED BLOCK CONDITIONS]")

    checks = preview.get(
        "checks",
        {}
    )

    expected = [

        (
            "mission_exists",
            checks.get(
                "mission_exists"
            )
            is True
        ),

        (
            "mission_is_open",
            checks.get(
                "mission_is_open"
            )
            is False
        ),

        (
            "mission_is_unassigned",
            checks.get(
                "mission_is_unassigned"
            )
            is False
        ),

        (
            "agent_exists",
            checks.get(
                "agent_exists"
            )
            is True
        ),

        (
            "agent_is_eligible",
            checks.get(
                "agent_is_eligible"
            )
            is True
        ),

    ]

    failed = False

    for name, passed in expected:

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
    print("[SAFETY ASSERTIONS]")

    safety_checks = [

        (
            "status == blocked",
            preview.get(
                "status"
            )
            == "blocked"
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
            "❌ NEGATIVE SAFETY TEST FAILED"
        )

        return 1

    print(
        "✅ NEGATIVE SAFETY TEST PASSED"
    )

    print()
    print(
        "MISSION #1 WAS CORRECTLY PROTECTED"
    )

    print(
        "NO INVALID ASSIGNMENT WAS PERFORMED"
    )

    print(
        "STATUS: ASSIGNMENT API SAFETY VALIDATED"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
