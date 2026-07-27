from pathlib import Path
import json
import hashlib
import shutil
from datetime import datetime, timezone

ROOT = Path(".")

BOARD_PATH = ROOT / "state" / "missions" / "board.json"
MANIFEST_PATH = ROOT / "state" / "takeover" / "manifest.json"
RESULTS_DIR = ROOT / "state" / "missions" / "results"
BACKUP_DIR = ROOT / "state" / "takeover" / "backups"


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


def main():

    print("=" * 80)
    print("           SLH MISSION RESULT RECORDER")
    print("                 CONTROLLED WRITE")
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

    print()
    print("[VALIDATION]")

    checks = [

        (
            "mission status == assigned",
            mission.get("status")
            == "assigned"
        ),

        (
            "assigned agent matches",
            str(assigned_to)
            == str(agent.get("id"))
        ),

        (
            "mission description == SYNC TEST",
            mission.get("desc")
            == "SYNC TEST"
        ),

    ]

    failed = False

    for name, result in checks:

        if result:

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
            "❌ RESULT RECORDING BLOCKED"
        )

        return 1

    now = datetime.now(
        timezone.utc
    )

    timestamp = now.strftime(
        "%Y%m%dT%H%M%SZ"
    )

    result_id = (
        f"mission-{mission_id}"
        f"-{timestamp}"
    )

    result = {

        "result_id": result_id,

        "mission_id": str(
            mission.get("id")
        ),

        "agent_id": str(
            agent.get("id")
        ),

        "agent_name": agent.get(
            "name"
        ),

        "operation": "SYNC TEST",

        "execution_status": "success",

        "execution_mode":
            "CONTROLLED LOCAL TEST",

        "result": {

            "mission_loaded": True,

            "agent_loaded": True,

            "assignment_confirmed": True,

            "synchronization_check":
                "passed",

        },

        "verified": False,

        "mission_completion":
            "pending",

        "persistence":
            "result_record_only",

        "external_network":
            False,

        "recorded_at":
            now.isoformat(),

    }

    canonical = json.dumps(
        result,
        sort_keys=True,
        ensure_ascii=False,
    )

    result["result_sha256"] = (
        sha256_text(canonical)
    )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    existing_results = list(
        RESULTS_DIR.glob("*.json")
    )

    if existing_results:

        backup_timestamp = now.strftime(
            "%Y%m%dT%H%M%SZ"
        )

        backup_dir = (
            BACKUP_DIR
            / f"results_before_recording_{backup_timestamp}"
        )

        backup_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        for path in existing_results:

            shutil.copy2(
                path,
                backup_dir / path.name
            )

        print()
        print(
            "✅ Existing results backed up:",
            backup_dir
        )

    result_path = (
        RESULTS_DIR
        / f"{result_id}.json"
    )

    if result_path.exists():

        print()
        print(
            "❌ RESULT ALREADY EXISTS:",
            result_path
        )

        return 1

    result_path.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print()
    print("[RESULT RECORDED]")

    print(
        "Result ID:",
        result_id
    )

    print(
        "Mission:",
        mission.get("desc")
    )

    print(
        "Agent:",
        agent.get("name")
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

    print(
        "SHA-256:",
        result.get(
            "result_sha256"
        )
    )

    print()
    print("[SAFETY BOUNDARY]")

    print(
        "✅ RESULT FILE CREATED"
    )

    print(
        "✅ BOARD NOT MODIFIED"
    )

    print(
        "✅ MANIFEST NOT MODIFIED"
    )

    print(
        "✅ MISSION NOT MARKED DONE"
    )

    print(
        "✅ AGENT NOT MODIFIED"
    )

    print()
    print("=" * 80)
    print("RESULT RECORDING COMPLETE")
    print("RESULT EXISTS BUT IS NOT YET VERIFIED")
    print("MISSION COMPLETION REMAINS PENDING")
    print("=" * 80)

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
