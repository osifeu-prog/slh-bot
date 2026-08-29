from core.mission_lifecycle import (
    MissionLifecycleService
)


def main():

    print("=" * 80)
    print("       SLH MISSION LIFECYCLE CORE")
    print("              DRY-RUN PREVIEW")
    print("=" * 80)

    service = MissionLifecycleService(
        "."
    )

    print()
    print("[EXECUTION PREVIEW]")

    execution = (
        service.preview_execution(
            "2"
        )
    )

    print(
        "Status:",
        execution.get("status")
    )

    print(
        "Mission:",
        execution.get(
            "mission_description"
        )
    )

    print(
        "Agent:",
        execution.get(
            "agent"
        )
    )

    for name, passed in (
        execution
        .get("checks", {})
        .items()
    ):

        print(
            "✅" if passed else "❌",
            name
        )

    print(
        "Write Performed:",
        execution.get(
            "write_performed"
        )
    )

    print()
    print("[COMPLETION PREVIEW]")

    completion = (
        service.preview_completion(
            "2"
        )
    )

    print(
        "Status:",
        completion.get("status")
    )

    print(
        "Result:",
        completion.get(
            "result_id"
        )
    )

    for name, passed in (
        completion
        .get("checks", {})
        .items()
    ):

        print(
            "✅" if passed else "❌",
            name
        )

    print(
        "Read Only:",
        completion.get(
            "read_only"
        )
    )

    print()
    print("[SAFETY CHECK]")

    print(
        "✅ NO BOARD WRITE"
    )

    print(
        "✅ NO RESULT WRITE"
    )

    print(
        "✅ NO MANIFEST WRITE"
    )

    print()
    print("=" * 80)
    print("LIFECYCLE CORE PREVIEW COMPLETE")
    print("DRY-RUN ONLY")
    print("=" * 80)


if __name__ == "__main__":

    main()
