from pathlib import Path
import json
import sys

ROOT = Path(".")

MANIFEST_PATH = (
    ROOT
    / "state"
    / "takeover"
    / "manifest.json"
)


def load_manifest():

    if not MANIFEST_PATH.exists():

        raise FileNotFoundError(
            f"Manifest not found: {MANIFEST_PATH}"
        )

    return json.loads(
        MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )


def find_agent(manifest, agent_id):

    agents = (
        manifest
        .get("agents", {})
        .get("items", [])
    )

    for agent in agents:

        if str(agent.get("id")) == str(agent_id):

            return agent

    return None


def find_mission(manifest, mission_id):

    missions = (
        manifest
        .get("missions", {})
        .get("open_items", [])
    )

    for mission in missions:

        if str(mission.get("id")) == str(mission_id):

            return mission

    return None


def main():

    print("=" * 80)
    print("              SLH ASSIGNMENT APPROVAL")
    print("                 APPROVAL GATE")
    print("=" * 80)

    manifest = load_manifest()

    # --------------------------------------------------------
    # EXPLICIT PROPOSED ASSIGNMENT
    # --------------------------------------------------------

    mission_id = "1"
    agent_id = "3"

    mission = find_mission(
        manifest,
        mission_id
    )

    agent = find_agent(
        manifest,
        agent_id
    )

    print()
    print("[REQUESTED ASSIGNMENT]")

    print(
        "Mission:",
        mission_id
    )

    print(
        "Agent:",
        agent_id
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    print()
    print("[VALIDATION]")

    if mission is None:

        print(
            "❌ MISSION NOT FOUND"
        )

        return 1

    print(
        "✅ Mission exists:",
        mission.get("description")
    )

    if agent is None:

        print(
            "❌ AGENT NOT FOUND"
        )

        return 1

    print(
        "✅ Agent exists:",
        agent.get("name")
    )

    state = agent.get(
        "state",
        "unknown"
    )

    print(
        "Agent state:",
        state
    )

    if state not in (
        "idle",
        "active"
    ):

        print(
            "❌ AGENT STATE NOT ELIGIBLE"
        )

        return 1

    print(
        "✅ Agent state eligible"
    )

    # --------------------------------------------------------
    # APPROVAL SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("                 APPROVAL REQUEST")
    print("=" * 80)

    print()
    print(
        "Mission:",
        f"#{mission.get('id')}"
    )

    print(
        "Description:",
        mission.get(
            "description"
        )
    )

    print(
        "Target Agent:",
        f"{agent.get('id')} "
        f"({agent.get('name')})"
    )

    print(
        "Current Agent State:",
        agent.get("state")
    )

    print()
    print(
        "PROPOSED EFFECT:"
    )

    print(
        f"Mission #{mission.get('id')} "
        f"would be assigned to "
        f"Agent {agent.get('id')}."
    )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "This script is an APPROVAL GATE only."
    )

    print(
        "It does NOT modify the database."
    )

    print(
        "It does NOT modify the mission board."
    )

    print(
        "It does NOT modify the agent."
    )

    print()
    print(
        "STATUS: APPROVAL REQUIRED"
    )

    print()
    print("=" * 80)
    print(
        "NO WRITE OPERATION PERFORMED"
    )
    print("=" * 80)

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
