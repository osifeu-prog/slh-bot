from core.mission_lifecycle import (
    MissionLifecycleService
)


def main():

    print("=" * 80)
    print("       SLH MISSION #4 CREATION PREVIEW")
    print("              READ-ONLY TEST")
    print("=" * 80)

    mission_id = "4"

    description = (
        "API LIFECYCLE INTEGRATION TEST"
    )

    reward = 0

    service = MissionLifecycleService(".")

    preview = (
        service.preview_mission_creation(
            mission_id=mission_id,
            description=description,
            reward=reward
        )
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
        "Reward:",
        preview.get("reward")
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
            "❌ MISSION #4 CREATION PREVIEW FAILED"
        )

        return 1

    print(
        "✅ MISSION #4 CREATION PREVIEW PASSED"
    )

    print()
    print(
        "MISSION #4 IS READY FOR CONTROLLED CREATION"
    )

    print(
        "NEXT: CREATE MISSION #4"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
