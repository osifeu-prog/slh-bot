from pathlib import Path
import json
import hashlib
import sys

ROOT = Path(".")

BOARD_PATH = ROOT / "state" / "missions" / "board.json"
MANIFEST_PATH = ROOT / "state" / "takeover" / "manifest.json"
RESULTS_DIR = ROOT / "state" / "missions" / "results"


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


def find_mission(board, mission_id):

    for mission in board.get(
        "missions",
        []
    ):

        if (
            isinstance(mission, dict)
            and str(mission.get("id"))
            == str(mission_id)
        ):

            return mission

    return None


def find_agent(manifest, agent_id):

    agents = (
        manifest
        .get("agents", {})
        .get("items", [])
    )

    for agent in agents:

        if (
            str(agent.get("id"))
            == str(agent_id)
        ):

            return agent

    return None


def find_latest_result(mission_id):

    results = []

    for path in RESULTS_DIR.glob(
        f"mission-{mission_id}-*.json"
    ):

        try:

            data = load_json(
                path
            )

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


def verify_result_integrity(result):

    stored_hash = result.get(
        "result_sha256"
    )

    if not stored_hash:

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
        ensure_ascii=False,
    )

    calculated_hash = sha256_text(
        canonical
    )

    return (
        calculated_hash
        == stored_hash
    )


def main():

    print("=" * 80)
    print("           SLH MISSION RESULT VERIFIER")
    print("                 READ-ONLY MODE")
    print("=" * 80)

    mission_id = "1"

    board = load_json(
        BOARD_PATH
    )

    manifest = load_json(
        MANIFEST_PATH
    )

    mission = find_mission(
        board,
        mission_id
    )

    if mission is None:

        print()
        print(
            "❌ MISSION NOT FOUND"
        )

        return 1

    result_entry = find_latest_result(
        mission_id
    )

    if result_entry is None:

        print()
        print(
            "❌ NO RESULT FOUND"
        )

        return 1

    recorded_at, result_path, result = (
        result_entry
    )

    assigned_to = mission.get(
        "assigned_to"
    )

    agent = find_agent(
        manifest,
        assigned_to
    )

    if agent is None:

        print()
        print(
            "❌ ASSIGNED AGENT NOT FOUND"
        )

        return 1

    print()
    print("[MISSION]")

    print(
        "Mission ID:",
        mission.get("id")
    )

    print(
        "Description:",
        mission.get("desc")
    )

    print(
        "Mission Status:",
        mission.get("status")
    )

    print(
        "Assigned To:",
        assigned_to
    )

    print()
    print("[RESULT]")

    print(
        "Result File:",
        result_path
    )

    print(
        "Result ID:",
        result.get("result_id")
    )

    print(
        "Execution Status:",
        result.get(
            "execution_status"
        )
    )

    print(
        "Result Agent:",
        result.get(
            "agent_name"
        )
    )

    print(
        "Verified Flag:",
        result.get(
            "verified"
        )
    )

    print()
    print("[VERIFICATION CHECKS]")

    checks = [

        (
            "result mission_id matches mission",
            str(
                result.get(
                    "mission_id"
                )
            )
            == str(
                mission.get("id")
            )
        ),

        (
            "result agent_id matches assignment",
            str(
                result.get(
                    "agent_id"
                )
            )
            == str(
                assigned_to
            )
        ),

        (
            "execution status is success",
            result.get(
                "execution_status"
            )
            == "success"
        ),

        (
            "synchronization check passed",
            result.get(
                "result",
                {}
            ).get(
                "synchronization_check"
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
            "mission remains assigned",
            mission.get(
                "status"
            )
            == "assigned"
        ),

        (
            "result is not already verified",
            result.get(
                "verified"
            )
            is False
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

    print()

    if failed:

        print(
            "❌ RESULT VERIFICATION FAILED"
        )

        print(
            "STATUS: MISSION NOT ELIGIBLE FOR COMPLETION"
        )

        return 1

    print(
        "✅ RESULT VERIFICATION PASSED"
    )

    print()
    print(
        "MISSION COMPLETION: ELIGIBLE"
    )

    print(
        "STATUS: READY FOR COMPLETION GATE"
    )

    print()
    print("[SAFETY BOUNDARY]")

    print(
        "⚪ NO RESULT FILE MODIFIED"
    )

    print(
        "⚪ NO MISSION MODIFIED"
    )

    print(
        "⚪ NO AGENT MODIFIED"
    )

    print(
        "⚪ NO MANIFEST MODIFIED"
    )

    print()
    print("=" * 80)
    print("RESULT VERIFICATION COMPLETE")
    print("READ-ONLY VERIFICATION ONLY")
    print("=" * 80)

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
