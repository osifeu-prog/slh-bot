from pathlib import Path
import json
import sys
from datetime import datetime, timezone

ROOT = Path(".")

BOARD_PATH = ROOT / "state" / "missions" / "board.json"
MANIFEST_PATH = ROOT / "state" / "takeover" / "manifest.json"


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


def find_mission(board, mission_id):

    for mission in board.get("missions", []):

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
    print("              SLH EXECUTION GATE")
    print("              CONTROLLED EXECUTION")
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

        print("❌ MISSION NOT FOUND")
        return 1

    assigned_to = mission.get(
        "assigned_to"
    )

    if assigned_to is None:

        print("❌ MISSION HAS NO ASSIGNED AGENT")
        return 1

    agent = find_agent(
        manifest,
        assigned_to
    )

    if agent is None:

        print("❌ ASSIGNED AGENT NOT FOUND")
        return 1

    print()
    print("[LIVE VALIDATION]")

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
        "Assigned Agent:",
        f"{agent.get('id')} "
        f"({agent.get('name')})"
    )

    print(
        "Agent State:",
        agent.get("state")
    )

    checks = [

        (
            "mission is assigned",
            mission.get("status")
            == "assigned"
        ),

        (
            "agent identity is valid",
            agent.get("id")
            == assigned_to
            or str(agent.get("id"))
            == str(assigned_to)
        ),

        (
            "agent is eligible",
            agent.get("state")
            in ("idle", "active")
        ),

        (
            "mission description is SYNC TEST",
            mission.get("desc")
            == "SYNC TEST"
        ),

    ]

    print()
    print("[EXECUTION CHECKS]")

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
        print("❌ EXECUTION GATE BLOCKED")
        return 1

    print()
    print("[EXECUTION AUTHORIZATION]")

    print(
        "Mission #1 is authorized for controlled execution."
    )

    print(
        "Target:",
        agent.get("name")
    )

    print(
        "Mode:",
        "CONTROLLED TEST"
    )

    print(
        "Timestamp:",
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    print()
    print("[SAFETY BOUNDARY]")

    print(
        "⚪ NO DATABASE WRITE"
    )

    print(
        "⚪ NO MISSION STATUS CHANGE"
    )

    print(
        "⚪ NO AGENT STATUS CHANGE"
    )

    print(
        "⚪ NO EXTERNAL NETWORK ACTION"
    )

    print()
    print("✅ EXECUTION GATE PASSED")
    print()
    print("STATUS: AUTHORIZED FOR CONTROLLED EXECUTION")

    print()
    print("=" * 80)
    print("EXECUTION GATE COMPLETE")
    print("AUTHORIZATION ONLY")
    print("NO MISSION EXECUTED BY THIS SCRIPT")
    print("=" * 80)

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
