from pathlib import Path
import json
import hashlib
import shutil
from datetime import datetime, timezone


ROOT = Path(".")

BOARD_PATH = (
    ROOT
    / "state"
    / "missions"
    / "board.json"
)

RESULTS_DIR = (
    ROOT
    / "state"
    / "missions"
    / "results"
)

BACKUP_DIR = (
    ROOT
    / "state"
    / "takeover"
    / "backups"
)


def load_json(path):

    if not path.exists():

        raise FileNotFoundError(
            f"File not found: {path}"
        )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def sha256_text(text):

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def find_mission(
    board,
    mission_id
):

    for mission in board.get(
        "missions",
        []
    ):

        if (
            isinstance(mission, dict)
            and str(
                mission.get("id")
            )
            == str(mission_id)
        ):

            return mission

    return None


def find_latest_result(
    mission_id
):

    results = []

    for path in RESULTS_DIR.glob(
        f"mission-{mission_id}-*.json"
    ):

        try:

            data = load_json(path)

            results.append(
                (
                    data.get(
                        "recorded_at",
                        ""
                    ),
                    path,
                    data
                )
            )

        except Exception:

            continue

    if not results:

        return None

    results.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return results[0]


def verify_result_integrity(
    result
):

    stored_hash = result.get(
        "result_sha256"
    )

    if not stored_hash:

        return False

    payload = dict(result)

    payload.pop(
        "result_sha256",
        None
    )

    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False
    )

    calculated_hash = sha256_text(
        canonical
    )

    return calculated_hash == stored_hash


def main():

    print("=" * 80)
    print("       SLH MISSION COMPLETION COMMIT")
    print("             CONTROLLED WRITE")
    print("=" * 80)

    mission_id = "2"

    board = load_json(
        BOARD_PATH
    )

    mission = find_mission(
        board,
        mission_id
    )

    result_entry = (
        find_latest_result(
            mission_id
        )
    )

    print()
    print("[FINAL PRE-WRITE VALIDATION]")

    if result_entry is None:

        print(
            "❌ RESULT NOT FOUND"
        )

        return 1

    recorded_at, result_path, result = (
        result_entry
    )

    checks = [

        (
            "mission exists",
            mission is not None
        ),

        (
            "mission status == assigned",
            mission is not None
            and mission.get(
                "status"
            )
            == "assigned"
        ),

        (
            "result mission matches mission",
            str(
                result.get(
                    "mission_id"
                )
            )
            == str(
                mission.get(
                    "id"
                )
            )
        ),

        (
            "result agent matches assignment",
            str(
                result.get(
                    "agent_id"
                )
            )
            == str(
                mission.get(
                    "assigned_to"
                )
            )
        ),

        (
            "execution status == success",
            result.get(
                "execution_status"
            )
            == "success"
        ),

        (
            "synchronization check == passed",
            result.get(
                "result",
                {}
            ).get(
                "synchronization_check"
            )
            == "passed"
        ),

        (
            "execution check == passed",
            result.get(
                "result",
                {}
            ).get(
                "execution_check"
            )
            == "passed"
        ),

        (
            "result hash is valid",
            verify_result_integrity(
                result
            )
        ),

        (
            "result is not already verified",
            result.get(
                "verified"
            )
            is False
        ),

        (
            "mission completion is pending",
            result.get(
                "mission_completion"
            )
            == "pending"
        ),

    ]

    failed = False

    for name, passed in checks:

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

    if failed:

        print()
        print(
            "❌ COMPLETION COMMIT BLOCKED"
        )

        return 1

    now = datetime.now(
        timezone.utc
    )

    timestamp = now.strftime(
        "%Y%m%dT%H%M%SZ"
    )

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    board_backup = (
        BACKUP_DIR
        / f"board_before_completion_2_{timestamp}.json"
    )

    result_backup = (
        BACKUP_DIR
        / f"result_before_completion_2_{timestamp}.json"
    )

    print()
    print("[BACKUP]")

    shutil.copy2(
        BOARD_PATH,
        board_backup
    )

    shutil.copy2(
        result_path,
        result_backup
    )

    print(
        "✅ Board backup:",
        board_backup
    )

    print(
        "✅ Result backup:",
        result_backup
    )

    print()
    print("[CONTROLLED WRITE]")

    mission["status"] = "done"

    result["verified"] = True

    result["mission_completion"] = (
        "completed"
    )

    result["completed_at"] = (
        now.isoformat()
    )

    payload = dict(result)

    payload.pop(
        "result_sha256",
        None
    )

    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False
    )

    result["result_sha256"] = (
        sha256_text(
            canonical
        )
    )

    BOARD_PATH.write_text(
        json.dumps(
            board,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    result_path.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(
        "✅ Mission status updated: done"
    )

    print(
        "✅ Result marked verified"
    )

    print(
        "✅ Mission completion marked completed"
    )

    print()
    print("[COMMIT RESULT]")

    print(
        "Mission:",
        f"#{mission.get('id')}"
    )

    print(
        "Status:",
        mission.get("status")
    )

    print(
        "Result:",
        result.get("result_id")
    )

    print(
        "Verified:",
        result.get("verified")
    )

    print(
        "Mission Completion:",
        result.get(
            "mission_completion"
        )
    )

    print(
        "Completed At:",
        result.get(
            "completed_at"
        )
    )

    print(
        "New Result SHA-256:",
        result.get(
            "result_sha256"
        )
    )

    print()
    print("[SAFETY BOUNDARY]")

    print(
        "✅ BOARD MODIFIED: ONE MISSION"
    )

    print(
        "✅ RESULT MODIFIED: ONE RESULT"
    )

    print(
        "✅ AGENT NOT MODIFIED"
    )

    print(
        "✅ MANIFEST NOT MODIFIED DIRECTLY"
    )

    print(
        "✅ BACKUPS CREATED BEFORE WRITE"
    )

    print(
        "✅ NO EXTERNAL NETWORK ACTION"
    )

    print()
    print("=" * 80)
    print("MISSION COMPLETION COMMIT COMPLETE")
    print("MISSION #2 IS NOW DONE")
    print("RESULT IS VERIFIED")
    print("MISSION CYCLE COMPLETED")
    print("=" * 80)

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
