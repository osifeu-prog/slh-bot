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

MANIFEST_PATH = (
    ROOT
    / "state"
    / "takeover"
    / "manifest.json"
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


def find_agent(
    manifest,
    agent_id
):

    agents = (
        manifest
        .get("agents", {})
        .get("items", [])
    )

    for agent in agents:

        if (
            str(
                agent.get("id")
            )
            == str(agent_id)
        ):

            return agent

    return None


def find_existing_success(
    mission_id
):

    if not RESULTS_DIR.exists():

        return None

    for path in RESULTS_DIR.glob(
        f"mission-{mission_id}-*.json"
    ):

        try:

            data = load_json(path)

            if (
                data.get(
                    "execution_status"
                )
                == "success"
            ):

                return path

        except Exception:

            continue

    return None


def main():

    print("=" * 80)
    print("       SLH MISSION EXECUTION COMMIT")
    print("             CONTROLLED WRITE")
    print("=" * 80)

    mission_id = "2"

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

    agent = None

    if mission is not None:

        agent = find_agent(
            manifest,
            mission.get(
                "assigned_to"
            )
        )

    existing_success = (
        find_existing_success(
            mission_id
        )
    )

    print()
    print("[FINAL PRE-WRITE VALIDATION]")

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
            "assigned agent exists",
            agent is not None
        ),

        (
            "agent state is eligible",
            agent is not None
            and agent.get(
                "state"
            )
            in (
                "idle",
                "active"
            )
        ),

        (
            "no previous successful result",
            existing_success is None
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
            "❌ EXECUTION COMMIT BLOCKED"
        )

        if existing_success:

            print(
                "Existing successful result:",
                existing_success
            )

        return 1

    now = datetime.now(
        timezone.utc
    )

    timestamp = now.strftime(
        "%Y%m%dT%H%M%SZ"
    )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    board_backup = (
        BACKUP_DIR
        / f"board_before_execution_{timestamp}.json"
    )

    print()
    print("[BACKUP]")

    shutil.copy2(
        BOARD_PATH,
        board_backup
    )

    print(
        "✅ Board backup:",
        board_backup
    )

    result_id = (
        f"mission-{mission_id}-{timestamp}"
    )

    result = {

        "result_id":
            result_id,

        "mission_id":
            mission_id,

        "agent_id":
            mission.get(
                "assigned_to"
            ),

        "recorded_at":
            now.isoformat(),

        "execution_status":
            "success",

        "execution_mode":
            "CONTROLLED_TEST",

        "result": {

            "description":
                "LIFECYCLE CORE TEST",

            "synchronization_check":
                "passed",

            "execution_check":
                "passed",

            "external_action":
                False,

        },

        "verified":
            False,

        "mission_completion":
            "pending",

    }

    canonical = json.dumps(
        result,
        sort_keys=True,
        ensure_ascii=False
    )

    result["result_sha256"] = (
        sha256_text(canonical)
    )

    result_path = (
        RESULTS_DIR
        / f"{result_id}.json"
    )

    print()
    print("[CONTROLLED WRITE]")

    result_path.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(
        "✅ Execution result created"
    )

    print(
        "✅ Result ID:",
        result_id
    )

    print(
        "✅ Execution Status:",
        result.get(
            "execution_status"
        )
    )

    print(
        "✅ Synchronization:",
        result.get(
            "result",
            {}
        ).get(
            "synchronization_check"
        )
    )

    print()
    print("[COMMIT RESULT]")

    print(
        "Mission:",
        f"#{mission.get('id')}"
    )

    print(
        "Agent:",
        agent.get("name")
    )

    print(
        "Status:",
        mission.get("status")
    )

    print(
        "Result:",
        result_path
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
        "✅ RESULT CREATED: ONE RESULT"
    )

    print(
        "✅ BOARD NOT MODIFIED"
    )

    print(
        "✅ AGENT NOT MODIFIED"
    )

    print(
        "✅ MANIFEST NOT MODIFIED DIRECTLY"
    )

    print(
        "✅ BACKUP CREATED BEFORE WRITE"
    )

    print(
        "✅ NO EXTERNAL NETWORK ACTION"
    )

    print()
    print("=" * 80)
    print("MISSION EXECUTION COMMIT COMPLETE")
    print("MISSION #2 EXECUTION RECORDED")
    print("READY FOR COMPLETION PREVIEW")
    print("=" * 80)

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
