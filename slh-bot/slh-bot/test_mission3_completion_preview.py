from pathlib import Path
import json
import hashlib

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


def verify_result_hash(
    result
):

    stored = result.get(
        "result_sha256"
    )

    if not stored:

        return False

    payload = dict(
        result
    )

    payload.pop(
        "result_sha256",
        None
    )

    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False
    )

    calculated = hashlib.sha256(
        canonical.encode(
            "utf-8"
        )
    ).hexdigest()

    return calculated == stored


def main():

    print("=" * 80)
    print("       SLH MISSION #3 COMPLETION PREVIEW")
    print("              READ-ONLY TEST")
    print("=" * 80)

    mission_id = "3"

    service = MissionLifecycleService(".")

    board = load_board()

    mission = find_mission(
        board,
        mission_id
    )

    print()
    print("[CURRENT MISSION STATE]")

    if mission is None:

        print(
            "❌ MISSION #3 NOT FOUND"
        )

        return 1

    print(
        "Mission:",
        mission.get("id")
    )

    print(
        "Description:",
        mission.get("desc")
    )

    print(
        "Status:",
        mission.get("status")
    )

    print(
        "Assigned To:",
        mission.get("assigned_to")
    )

    print()
    print("[EXECUTION RESULT DISCOVERY]")

    results_dir = Path(
        "state/missions/results"
    )

    result_files = sorted(
        results_dir.glob(
            f"mission-{mission_id}-*.json"
        )
    )

    if not result_files:

        print(
            "❌ EXECUTION RESULT NOT FOUND"
        )

        return 1

    result_path = result_files[-1]

    result = json.loads(
        result_path.read_text(
            encoding="utf-8"
        )
    )

    print(
        "Result:",
        result.get("result_id")
    )

    print(
        "Execution Status:",
        result.get(
            "execution_status"
        )
    )

    print(
        "Verified:",
        result.get(
            "verified"
        )
    )

    print(
        "Mission Completion:",
        result.get(
            "mission_completion"
        )
    )

    print()
    print("[COMPLETION PREVIEW]")

    preview = service.preview_completion(
        mission_id=mission_id
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
        "Current Status:",
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
        "Proposed Completion:",
        preview.get(
            "proposed_completion"
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
    print("[RESULT INTEGRITY CHECK]")

    integrity_checks = [

        (
            "result file exists",
            result_path.exists()
        ),

        (
            "result execution_status == success",
            result.get(
                "execution_status"
            )
            == "success"
        ),

        (
            "result verified == True",
            result.get(
                "verified"
            )
            is True
        ),

        (
            "mission_completion == pending",
            result.get(
                "mission_completion"
            )
            == "pending"
        ),

        (
            "result hash valid",
            verify_result_hash(
                result
            )
        ),

    ]

    for name, passed in integrity_checks:

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
            "proposed_status == completed",
            preview.get(
                "proposed_status"
            )
            == "completed"
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
            "❌ MISSION #3 COMPLETION PREVIEW FAILED"
        )

        return 1

    print(
        "✅ MISSION #3 COMPLETION PREVIEW PASSED"
    )

    print()
    print(
        "MISSION #3 IS READY FOR CONTROLLED COMPLETION"
    )

    print(
        "NEXT: IMPLEMENT COMPLETION COMMIT API"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
