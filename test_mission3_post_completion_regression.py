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


def snapshot_board():

    return BOARD_PATH.read_text(
        encoding="utf-8"
    )


def main():

    print("=" * 80)
    print("   SLH MISSION #3 POST-COMPLETION REGRESSION TEST")
    print("          IDEMPOTENCY & WRITE PROTECTION")
    print("=" * 80)

    mission_id = "3"

    service = MissionLifecycleService(".")

    board_before = load_board()

    mission_before = find_mission(
        board_before,
        mission_id
    )

    print()
    print("[CURRENT STATE]")

    if mission_before is None:

        print(
            "❌ MISSION #3 NOT FOUND"
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
            "mission status == completed",
            mission_before.get(
                "status"
            )
            == "completed"
        ),

    ]

    for name, passed in pre_checks:

        print(
            "✅" if passed else "❌",
            name
        )

        if not passed:

            print(
                "❌ INVALID REGRESSION TEST STATE"
            )

            return 1

    board_snapshot = snapshot_board()

    print()
    print("[RE-EXECUTION PREVIEW]")

    execution_preview = (
        service.preview_execution(
            mission_id=mission_id
        )
    )

    print(
        "Status:",
        execution_preview.get(
            "status"
        )
    )

    for name, passed in (
        execution_preview.get(
            "checks",
            {}
        )
    ).items():

        print(
            "✅" if passed else "❌",
            name
        )

    execution_preview_checks = [

        (
            "execution preview blocked",
            execution_preview.get(
                "status"
            )
            == "blocked"
        ),

        (
            "execution preview write_performed == False",
            execution_preview.get(
                "write_performed"
            )
            is False
        ),

    ]

    failed = False

    for name, passed in execution_preview_checks:

        print(
            "✅" if passed else "❌",
            name
        )

        if not passed:

            failed = True

    print()
    print("[RE-EXECUTION COMMIT ATTEMPT]")

    execution_result = (
        service.execute_mission(
            mission_id=mission_id
        )
    )

    print(
        "Status:",
        execution_result.get(
            "status"
        )
    )

    print(
        "Reason:",
        execution_result.get(
            "reason"
        )
    )

    print(
        "Write Performed:",
        execution_result.get(
            "write_performed"
        )
    )

    execution_commit_checks = [

        (
            "execution commit blocked",
            execution_result.get(
                "status"
            )
            == "blocked"
        ),

        (
            "execution commit write_performed == False",
            execution_result.get(
                "write_performed"
            )
            is False
        ),

    ]

    for name, passed in execution_commit_checks:

        print(
            "✅" if passed else "❌",
            name
        )

        if not passed:

            failed = True

    print()
    print("[RE-COMPLETION PREVIEW]")

    completion_preview = (
        service.preview_completion(
            mission_id=mission_id
        )
    )

    print(
        "Status:",
        completion_preview.get(
            "status"
        )
    )

    print(
        "Current Status:",
        completion_preview.get(
            "current_status"
        )
    )

    print(
        "Proposed Status:",
        completion_preview.get(
            "proposed_status"
        )
    )

    completion_preview_checks = [

        (
            "completion preview blocked",
            completion_preview.get(
                "status"
            )
            == "blocked"
        ),

        (
            "completion preview write_performed == False",
            completion_preview.get(
                "write_performed"
            )
            is False
        ),

    ]

    for name, passed in completion_preview_checks:

        print(
            "✅" if passed else "❌",
            name
        )

        if not passed:

            failed = True

    print()
    print("[RE-COMPLETION COMMIT ATTEMPT]")

    completion_result = (
        service.complete_mission(
            mission_id=mission_id
        )
    )

    print(
        "Status:",
        completion_result.get(
            "status"
        )
    )

    print(
        "Reason:",
        completion_result.get(
            "reason"
        )
    )

    print(
        "Write Performed:",
        completion_result.get(
            "write_performed"
        )
    )

    completion_commit_checks = [

        (
            "completion commit blocked",
            completion_result.get(
                "status"
            )
            == "blocked"
        ),

        (
            "completion commit write_performed == False",
            completion_result.get(
                "write_performed"
            )
            is False
        ),

    ]

    for name, passed in completion_commit_checks:

        print(
            "✅" if passed else "❌",
            name
        )

        if not passed:

            failed = True

    print()
    print("[BOARD WRITE PROTECTION CHECK]")

    board_after = snapshot_board()

    board_unchanged = (
        board_snapshot
        == board_after
    )

    print(
        "✅" if board_unchanged else "❌",
        "board unchanged"
    )

    if not board_unchanged:

        failed = True

    final_board = load_board()

    final_mission = find_mission(
        final_board,
        mission_id
    )

    final_checks = [

        (
            "final status remains completed",
            final_mission is not None
            and final_mission.get(
                "status"
            )
            == "completed"
        ),

        (
            "completed_at preserved",
            final_mission is not None
            and bool(
                final_mission.get(
                    "completed_at"
                )
            )
        ),

    ]

    print()
    print("[FINAL STATE INTEGRITY]")

    for name, passed in final_checks:

        print(
            "✅" if passed else "❌",
            name
        )

        if not passed:

            failed = True

    print()

    if failed:

        print(
            "❌ POST-COMPLETION REGRESSION TEST FAILED"
        )

        return 1

    print(
        "✅ POST-COMPLETION REGRESSION TEST PASSED"
    )

    print()
    print(
        "MISSION #3 IS IDEMPOTENT"
    )

    print(
        "RE-EXECUTION BLOCKED"
    )

    print(
        "RE-COMPLETION BLOCKED"
    )

    print(
        "NO UNAUTHORIZED BOARD WRITE DETECTED"
    )

    print()
    print(
        "STATUS: LIFECYCLE WRITE PROTECTION VERIFIED"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
