from pathlib import Path
import json
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


def main():

    print("=" * 80)
    print("       SLH MISSION ASSIGNMENT COMMIT")
    print("             CONTROLLED WRITE")
    print("=" * 80)

    mission_id = "2"
    agent_id = "3"

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

    agent = find_agent(
        manifest,
        agent_id
    )

    print()
    print("[FINAL PRE-WRITE VALIDATION]")

    checks = [

        (
            "mission exists",
            mission is not None
        ),

        (
            "mission status == open",
            mission is not None
            and mission.get(
                "status"
            )
            == "open"
        ),

        (
            "mission is unassigned",
            mission is not None
            and mission.get(
                "assigned_to"
            )
            is None
        ),

        (
            "agent exists",
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
            "❌ ASSIGNMENT COMMIT BLOCKED"
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

    backup_path = (
        BACKUP_DIR
        / f"board_before_assignment_{timestamp}.json"
    )

    print()
    print("[BACKUP]")

    shutil.copy2(
        BOARD_PATH,
        backup_path
    )

    print(
        "✅ Board backup:",
        backup_path
    )

    print()
    print("[CONTROLLED WRITE]")

    mission["status"] = "assigned"

    mission["assigned_to"] = agent_id

    mission["assigned_at"] = (
        now.isoformat()
    )

    BOARD_PATH.write_text(
        json.dumps(
            board,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(
        "✅ Mission #2 status updated:"
    )

    print(
        "   open → assigned"
    )

    print(
        "✅ Mission #2 assigned to Agent 3"
    )

    print()
    print("[COMMIT RESULT]")

    print(
        "Mission:",
        f"#{mission.get('id')}"
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

    print(
        "Assigned At:",
        mission.get("assigned_at")
    )

    print()
    print("[SAFETY BOUNDARY]")

    print(
        "✅ BOARD MODIFIED: ONE MISSION"
    )

    print(
        "✅ BACKUP CREATED BEFORE WRITE"
    )

    print(
        "✅ MANIFEST NOT MODIFIED DIRECTLY"
    )

    print(
        "✅ AGENT NOT MODIFIED"
    )

    print(
        "✅ NO EXTERNAL NETWORK ACTION"
    )

    print()
    print("=" * 80)
    print("MISSION ASSIGNMENT COMMIT COMPLETE")
    print("MISSION #2 IS NOW ASSIGNED")
    print("READY FOR MANIFEST REFRESH")
    print("=" * 80)

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
