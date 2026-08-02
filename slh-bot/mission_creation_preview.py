from core.mission_lifecycle import (
    MissionLifecycleService
)


def main():

    print("=" * 80)
    print("       SLH MISSION CREATION PREVIEW")
    print("              READ-ONLY MODE")
    print("=" * 80)

    service = MissionLifecycleService(
        "."
    )

    preview = (
        service.preview_mission_creation(
            mission_id="2",
            description="LIFECYCLE CORE TEST",
            assigned_to=None
        )
    )

    print()
    print("[PROPOSED MISSION]")

    print(
        "Mission ID:",
        preview.get("mission_id")
    )

    print(
        "Description:",
        preview.get("description")
    )

    print(
        "Initial Status:",
        preview.get("initial_status")
    )

    print(
        "Assigned To:",
        preview.get("assigned_to")
    )

    print()
    print("[VALIDATION CHECKS]")

    failed = False

    for name, passed in (
        preview
        .get("checks", {})
        .items()
    ):

        if passed:
            print("✅", name)
        else:
            print("❌", name)
            failed = True

    print()

    if failed:

        print(
            "❌ MISSION CREATION PREVIEW BLOCKED"
        )

        return 1

    print(
        "✅ MISSION CREATION PREVIEW PASSED"
    )

    print()
    print("[SAFETY BOUNDARY]")

    print(
        "⚪ BOARD WRITE: NO"
    )

    print(
        "⚪ MANIFEST WRITE: NO"
    )

    print(
        "⚪ AGENT MODIFICATION: NO"
    )

    print(
        "⚪ EXTERNAL NETWORK: NO"
    )

    print(
        "⚪ READ ONLY: YES"
    )

    print()
    print("=" * 80)
    print("MISSION CREATION PREVIEW COMPLETE")
    print("STATUS: READY FOR CONTROLLED CREATION COMMIT")
    print("=" * 80)

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
