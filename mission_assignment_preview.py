from core.mission_lifecycle import (
    MissionLifecycleService
)


def main():

    print("=" * 80)
    print("       SLH MISSION ASSIGNMENT PREVIEW")
    print("              READ-ONLY MODE")
    print("=" * 80)

    mission_id = "2"
    agent_id = "3"

    service = MissionLifecycleService(
        "."
    )

    board, manifest = (
        service.load_state()
    )

    mission = service.find_mission(
        board,
        mission_id
    )

    agent = service.find_agent(
        manifest,
        agent_id
    )

    print()
    print("[PROPOSED ASSIGNMENT]")

    print(
        "Mission:",
        f"#{mission.get('id')}"
        if mission
        else "MISSING"
    )

    print(
        "Description:",
        mission.get('desc')
        if mission
        else "MISSING"
    )

    print(
        "Current Status:",
        mission.get('status')
        if mission
        else "MISSING"
    )

    print(
        "Current Assigned To:",
        mission.get('assigned_to')
        if mission
        else "MISSING"
    )

    print(
        "Target Agent:",
        f"{agent.get('id')} "
        f"({agent.get('name')})"
        if agent
        else "MISSING"
    )

    print()
    print("[ASSIGNMENT VALIDATION]")

    checks = {

        "mission_exists":
            mission is not None,

        "mission_is_open":
            mission is not None
            and mission.get(
                "status"
            ) == "open",

        "mission_is_unassigned":
            mission is not None
            and mission.get(
                "assigned_to"
            ) is None,

        "agent_exists":
            agent is not None,

        "agent_is_eligible":
            agent is not None
            and agent.get(
                "state"
            )
            in (
                "idle",
                "active"
            ),

    }

    failed = False

    for name, passed in (
        checks.items()
    ):

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
            "❌ ASSIGNMENT PREVIEW BLOCKED"
        )

        return 1

    print(
        "✅ ASSIGNMENT PREVIEW PASSED"
    )

    print()
    print("[PROPOSED STATE CHANGE]")

    print(
        "Mission Status:",
        "open → assigned"
    )

    print(
        "Assigned To:",
        "None → Agent 3"
    )

    print()
    print("[SAFETY BOUNDARY]")

    print(
        "⚪ BOARD WRITE: NO"
    )

    print(
        "⚪ MANIFEST WRITE: NO"
    )

    print(
        "⚪ AGENT MODIFICATION: NO"
    )

    print(
        "⚪ EXTERNAL NETWORK: NO"
    )

    print(
        "⚪ READ ONLY: YES"
    )

    print()
    print("=" * 80)
    print("ASSIGNMENT PREVIEW COMPLETE")
    print("STATUS: READY FOR CONTROLLED ASSIGNMENT COMMIT")
    print("=" * 80)

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
