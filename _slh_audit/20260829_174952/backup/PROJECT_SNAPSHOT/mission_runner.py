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


def execute_sync_test(mission, agent):

    started_at = datetime.now(
        timezone.utc
    ).isoformat()

    result = {
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

        "status": "success",

        "result": {
            "mission_loaded": True,
            "agent_loaded": True,
            "assignment_confirmed": True,
            "synchronization_check": "passed",
        },

        "started_at": started_at,

        "completed_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "persistence": "none",

        "external_network": False,

    }

    return result


def main():

    print("=" * 80)
    print("              SLH MISSION RUNNER")
    print("              CONTROLLED TEST MODE")
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
    print("[RUNTIME VALIDATION]")

    checks = [

        (
            "mission status == assigned",
            mission.get("status")
            == "assigned"
        ),

        (
            "mission assigned_to == agent",
            str(assigned_to)
            == str(agent.get("id"))
        ),

        (
            "agent state eligible",
            agent.get("state")
            in ("idle", "active")
        ),

        (
            "mission == SYNC TEST",
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
            "❌ RUNTIME VALIDATION FAILED"
        )

        return 1

    print()
    print("[EXECUTION]")

    print(
        "Mission:",
        mission.get("desc")
    )

    print(
        "Agent:",
        agent.get("name")
    )

    print(
        "Mode:",
        "CONTROLLED LOCAL TEST"
    )

    result = execute_sync_test(
        mission,
        agent
    )

    print()
    print("[RESULT]")

    print(
        "Status:",
        result.get("status")
    )

    print(
        "Synchronization Check:",
        result.get(
            "result",
            {}
        ).get(
            "synchronization_check"
        )
    )

    print(
        "Persistence:",
        result.get(
            "persistence"
        )
    )

    print(
        "External Network:",
        result.get(
            "external_network"
        )
    )

    print()
    print("[SAFETY VERIFICATION]")

    print(
        "✅ NO DATABASE WRITE"
    )

    print(
        "✅ NO MISSION STATUS CHANGE"
    )

    print(
        "✅ NO AGENT STATUS CHANGE"
    )

    print(
        "✅ NO EXTERNAL NETWORK ACTION"
    )

    print(
        "✅ RESULT KEPT IN MEMORY ONLY"
    )

    print()
    print("=" * 80)
    print("MISSION EXECUTION COMPLETE")
    print("CONTROLLED SYNC TEST PASSED")
    print("NO PERSISTENCE PERFORMED")
    print("=" * 80)

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
