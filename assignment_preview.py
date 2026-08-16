from pathlib import Path
import json

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


def main():

    print("=" * 80)
    print("              SLH ASSIGNMENT PREVIEW")
    print("                 READ-ONLY MODE")
    print("=" * 80)

    manifest = load_manifest()

    agents = (
        manifest
        .get("agents", {})
        .get("items", [])
    )

    missions = (
        manifest
        .get("missions", {})
        .get("open_items", [])
    )

    if not missions:

        print()
        print("✅ NO OPEN MISSIONS")
        return 0

    for mission in missions:

        mission_id = mission.get("id")
        description = mission.get(
            "description",
            ""
        )

        text = str(description).lower()

        # ----------------------------------------------------
        # CURRENT RESPONSIBILITY MATCH
        # ----------------------------------------------------

        candidates = []

        for agent in agents:

            name = str(
                agent.get("name", "")
            ).lower()

            state = agent.get(
                "state",
                "unknown"
            )

            score = 0

            capabilities = []

            if "sync" in name:

                capabilities.append(
                    "sync"
                )

            if "token" in name:

                capabilities.append(
                    "token"
                )

            if "doctor" in name:

                capabilities.append(
                    "doctor"
                )

            if (
                "system" in name
                or "guard" in name
            ):

                capabilities.append(
                    "system"
                )

            if (
                "sync" in text
                and "sync" in capabilities
            ):

                score += 10

            if state == "idle":

                score += 2

            elif state == "active":

                score += 1

            candidates.append(
                (
                    score,
                    agent,
                    capabilities
                )
            )

        candidates.sort(
            key=lambda item: item[0],
            reverse=True
        )

        best_score, best_agent, capabilities = (
            candidates[0]
        )

        agent_id = best_agent.get(
            "id"
        )

        agent_name = best_agent.get(
            "name"
        )

        print()
        print("╔" + "═" * 78 + "╗")
        print(
            "║"
            + " ASSIGNMENT PREVIEW".center(78)
            + "║"
        )
        print("╠" + "═" * 78 + "╣")

        print(
            f"║ Mission ID:        #{mission_id}"
            .ljust(79)
            + "║"
        )

        print(
            f"║ Description:       {description}"
            .ljust(79)
            + "║"
        )

        print("║" + " " * 78 + "║")

        print(
            f"║ Recommended ID:    {agent_id}"
            .ljust(79)
            + "║"
        )

        print(
            f"║ Recommended Agent: {agent_name}"
            .ljust(79)
            + "║"
        )

        print(
            f"║ Current State:     {best_agent.get('state')}"
            .ljust(79)
            + "║"
        )

        print(
            f"║ Score:             {best_score}"
            .ljust(79)
            + "║"
        )

        print(
            f"║ Capabilities:      {capabilities}"
            .ljust(79)
            + "║"
        )

        print("║" + " " * 78 + "║")

        print(
            "║ Proposed Action:   "
            f"assign mission #{mission_id} → "
            f"agent {agent_id}"
            .ljust(79)
            + "║"
        )

        print(
            "║ Canonical Target:  "
            f"{agent_id} ({agent_name})"
            .ljust(79)
            + "║"
        )

        print("║" + " " * 78 + "║")

        print(
            "║ STATUS:            WAITING FOR APPROVAL"
            .ljust(79)
            + "║"
        )

        print("╚" + "═" * 78 + "╝")

        print()
        print("SAFETY CHECK:")
        print("⚪ NO AUTOMATIC ASSIGNMENT")
        print("⚪ NO DATABASE WRITE")
        print("⚪ NO BOARD MODIFICATION")
        print("⚪ NO AGENT MODIFICATION")
        print("⚪ NO MISSION MODIFICATION")

    print()
    print("=" * 80)
    print("ASSIGNMENT PREVIEW COMPLETE")
    print("READ-ONLY ANALYSIS ONLY")
    print("=" * 80)

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
