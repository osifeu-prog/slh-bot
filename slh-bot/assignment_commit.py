from pathlib import Path
import json
import shutil
from datetime import datetime, timezone

ROOT = Path(".")

MANIFEST_PATH = ROOT / "state" / "takeover" / "manifest.json"
BOARD_PATH = ROOT / "state" / "missions" / "board.json"
BACKUP_DIR = ROOT / "state" / "takeover" / "backups"


def load_json(path, default=None):
    if not path.exists():
        return default

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def main():

    print("=" * 80)
    print("              SLH ASSIGNMENT COMMIT")
    print("                 CONTROLLED WRITE")
    print("=" * 80)

    manifest = load_json(
        MANIFEST_PATH,
        {}
    )

    board = load_json(
        BOARD_PATH,
        {}
    )

    if not manifest:
        print("❌ MANIFEST NOT FOUND")
        return 1

    if not isinstance(board, dict):
        print("❌ MISSION BOARD INVALID")
        return 1

    mission_id = "1"
    agent_id = "3"

    missions = board.get(
        "missions",
        []
    )

    target_mission = None

    for mission in missions:

        if (
            isinstance(mission, dict)
            and str(mission.get("id"))
            == mission_id
        ):
            target_mission = mission
            break

    if target_mission is None:
        print("❌ MISSION NOT FOUND IN BOARD")
        return 1

    if target_mission.get("status") != "open":
        print(
            "❌ MISSION IS NOT OPEN:",
            target_mission.get("status")
        )
        return 1

    agents = (
        manifest
        .get("agents", {})
        .get("items", [])
    )

    target_agent = None

    for agent in agents:

        if str(agent.get("id")) == agent_id:
            target_agent = agent
            break

    if target_agent is None:
        print("❌ AGENT NOT FOUND IN MANIFEST")
        return 1

    if target_agent.get("state") not in (
        "idle",
        "active"
    ):
        print(
            "❌ AGENT NOT ELIGIBLE:",
            target_agent.get("state")
        )
        return 1

    print()
    print("[VALIDATED]")
    print(
        "Mission:",
        f"#{mission_id}",
        target_mission.get("desc")
    )

    print(
        "Agent:",
        f"{agent_id}",
        target_agent.get("name")
    )

    print()
    print("[BACKUP]")

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    backup_path = (
        BACKUP_DIR
        / f"board_before_assignment_{timestamp}.json"
    )

    shutil.copy2(
        BOARD_PATH,
        backup_path
    )

    print(
        "✅ Backup created:",
        backup_path
    )

    print()
    print("[WRITE]")

    target_mission["assigned_to"] = agent_id
    target_mission["status"] = "assigned"

    target_mission[
        "assigned_at"
    ] = datetime.now(
        timezone.utc
    ).isoformat()

    BOARD_PATH.write_text(
        json.dumps(
            board,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(
        "✅ Mission assigned"
    )

    print()
    print("[RESULT]")
    print(
        f"Mission #{mission_id}"
    )

    print(
        "Status:",
        target_mission.get("status")
    )

    print(
        "Assigned To:",
        target_mission.get("assigned_to")
    )

    print()
    print("=" * 80)
    print("CONTROLLED ASSIGNMENT COMPLETE")
    print("ONE MISSION MODIFIED")
    print("ONE ASSIGNMENT FIELD MODIFIED")
    print("BACKUP CREATED BEFORE WRITE")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
