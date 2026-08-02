from pathlib import Path
import json
import sys

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


def main():

    print("=" * 80)
    print("           SLH MISSION EXECUTION PREVIEW")
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
            "❌ MISSION NOT FOUND:",
            mission_id
        )

        return 1

    assigned_to = mission.get(
        "assigned_to"
    )

    if assigned_to is None:

        print()
        print(
            "❌ MISSION HAS NO ASSIGNED AGENT"
        )

        return 1

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

    status = mission.get(
        "status"
    )

    print()
    print("[MISSION]")

    print(
        "ID:",
        mission.get("id")
    )

    print(
        "Description:",
        mission.get("desc")
    )

    print(
        "Status:",
        status
    )

    print(
        "Assigned To:",
        assigned_to
    )

    print()
    print("[AGENT]")

    print(
        "ID:",
        agent.get("id")
    )

    print(
        "Name:",
        agent.get("name")
    )

    print(
        "Role:",
        agent.get("role")
    )

    print(
        "State:",
        agent.get("state")
    )

    print()
    print("[EXECUTION ELIGIBILITY]")

    checks = [

        (
            "mission status is assigned",
            status == "assigned"
        ),

        (
            "assigned agent exists",
            agent is not None
        ),

        (
            "agent state is eligible",
            agent.get("state")
            in (
                "idle",
                "active"
            )
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

    print()
    print("[PROPOSED EXECUTION]")

    print(
        "Mission #1: SYNC TEST"
    )

    print(
        "Execution target: SyncAgent"
    )

    print(
        "Execution mode: controlled test"
    )

    print(
        "Expected result: synchronization check"
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
        "⚪ NO RESULT RECORDING"
    )

    if failed:

        print()
        print(
            "❌ EXECUTION NOT ELIGIBLE"
        )

        return 1

    print()
    print(
        "✅ EXECUTION ELIGIBILITY PASSED"
    )

    print()
    print(
        "STATUS: READY FOR EXECUTION GATE"
    )

    print()
    print("=" * 80)
    print(
        "EXECUTION PREVIEW COMPLETE"
    )
    print(
        "READ-ONLY ANALYSIS ONLY"
    )
    print("=" * 80)

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
