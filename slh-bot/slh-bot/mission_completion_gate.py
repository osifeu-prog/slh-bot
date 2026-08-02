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
    print("           SLH MISSION COMPLETION GATE")
    print("                 APPROVAL GATE")
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

        print(
            "❌ MISSION NOT FOUND"
        )

        return 1

    assigned_to = mission.get(
        "assigned_to"
    )

    agent = find_agent(
        manifest,
        assigned_to
    )

    if agent is None:

        print(
            "❌ ASSIGNED AGENT NOT FOUND"
        )

        return 1

    result_entry = find_latest_result(
        mission_id
    )

    if result_entry is None:

        print(
            "❌ RESULT NOT FOUND"
        )

        return 1

    recorded_at, result_path, result = (
        result_entry
    )

    print()
    print("[COMPLETION REQUEST]")

    print(
        "Mission:",
        f"#{mission.get('id')}"
    )

    print(
        "Description:",
        mission.get("desc")
    )

    print(
        "Current Status:",
        mission.get("status")
    )

    print(
        "Assigned Agent:",
        f"{agent.get('id')} "
        f"({agent.get('name')})"
    )

    print(
        "Result:",
        result.get("result_id")
    )

    print()
    print("[COMPLETION VALIDATION]")

    checks = [

        (
            "mission status == assigned",
            mission.get("status")
            == "assigned"
        ),

        (
            "mission has assigned agent",
            assigned_to is not None
        ),

        (
            "assigned agent exists",
            agent is not None
        ),

        (
            "result mission matches mission",
            str(
                result.get("mission_id")
            )
            == str(
                mission.get("id")
            )
        ),

        (
            "result agent matches assignment",
            str(
                result.get("agent_id")
            )
            == str(
                assigned_to
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

    print()

    if failed:

        print(
            "❌ COMPLETION GATE BLOCKED"
        )

        print(
            "STATUS: MISSION CANNOT BE COMPLETED"
        )

        return 1

    print(
        "✅ ALL COMPLETION CHECKS PASSED"
    )

    print()
    print("[PROPOSED COMPLETION]")

    print(
        f"Mission #{mission.get('id')}"
    )

    print(
        "Current Status:",
        mission.get("status")
    )

    print(
        "Proposed Status:",
        "done"
    )

    print(
        "Result Verified:",
        "true"
    )

    print(
        "Mission Completion:",
        "completed"
    )

    print()
    print("[SAFETY BOUNDARY]")

    print(
        "⚪ NO BOARD WRITE"
    )

    print(
        "⚪ NO RESULT WRITE"
    )

    print(
        "⚪ NO MANIFEST WRITE"
    )

    print(
        "⚪ NO AGENT WRITE"
    )

    print()
    print(
        "STATUS: READY FOR COMPLETION COMMIT"
    )

    print()
    print("=" * 80)
    print("COMPLETION GATE PASSED")
    print("APPROVAL ONLY")
    print("NO COMPLETION COMMITTED")
    print("=" * 80)

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
