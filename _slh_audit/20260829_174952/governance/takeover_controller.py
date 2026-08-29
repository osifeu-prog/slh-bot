from pathlib import Path
import json
from datetime import datetime, timezone

ROOT = Path(".")
MANIFEST_PATH = ROOT / "state" / "takeover" / "manifest.json"
DB_PATH = ROOT / "state" / "db.json"
BOARD_PATH = ROOT / "state" / "missions" / "board.json"
MEMORY_PATH = ROOT / "state" / "system_memory.json"


def load_json(path, default):
    try:
        if not path.exists():
            return default

        return json.loads(
            path.read_text(encoding="utf-8")
        )

    except Exception:
        return default


def main():

    print("=" * 80)
    print("              SLH TAKEOVER CONTROLLER")
    print("                 READ-ONLY MODE")
    print("=" * 80)

    # --------------------------------------------------------
    # MANIFEST
    # --------------------------------------------------------

    manifest = load_json(
        MANIFEST_PATH,
        {}
    )

    if not manifest:

        print()
        print("❌ TAKEOVER MANIFEST NOT FOUND")
        print("Expected:", MANIFEST_PATH)
        return 1

    system = manifest.get(
        "system",
        {}
    )

    print()
    print("[SYSTEM]")
    print(
        "Name:",
        system.get("name", "UNKNOWN")
    )

    print(
        "Takeover Status:",
        system.get(
            "takeover_status",
            "UNKNOWN"
        )
    )

    print(
        "Manifest Version:",
        manifest.get(
            "manifest_version",
            "UNKNOWN"
        )
    )

    print(
        "Generated:",
        system.get(
            "generated_at",
            "UNKNOWN"
        )
    )

    # --------------------------------------------------------
    # AGENTS
    # --------------------------------------------------------

    agents = manifest.get(
        "agents",
        {}
    )

    print()
    print("[AGENTS]")
    print(
        "Total:",
        agents.get(
            "total",
            0
        )
    )

    print(
        "States:",
        agents.get(
            "states",
            {}
        )
    )

    items = agents.get(
        "items",
        []
    )

    for agent in items:

        print(
            f"  [{agent.get('id')}] "
            f"{agent.get('name')} | "
            f"state={agent.get('state')} | "
            f"inbox={agent.get('inbox_count')}"
        )

    # --------------------------------------------------------
    # MISSIONS
    # --------------------------------------------------------

    missions = manifest.get(
        "missions",
        {}
    )

    print()
    print("[MISSIONS]")

    print(
        "Total:",
        missions.get(
            "total",
            0
        )
    )

    print(
        "Open:",
        missions.get(
            "open",
            0
        )
    )

    print(
        "Assigned:",
        missions.get(
            "assigned",
            0
        )
    )

    print(
        "Done:",
        missions.get(
            "done",
            0
        )
    )

    open_items = missions.get(
        "open_items",
        []
    )

    if open_items:

        print()
        print("OPEN WORK:")

        for mission in open_items:

            print(
                f"  #{mission.get('id')} | "
                f"{mission.get('description')} | "
                f"assigned="
                f"{mission.get('assigned_to')} | "
                f"reward="
                f"{mission.get('reward')}"
            )

    # --------------------------------------------------------
    # TASK SYSTEM
    # --------------------------------------------------------

    tasks = manifest.get(
        "tasks",
        {}
    )

    print()
    print("[TASK SYSTEM]")

    print(
        "Service:",
        "AVAILABLE"
        if tasks.get("service_exists")
        else "MISSING"
    )

    print(
        "Handler:",
        "AVAILABLE"
        if tasks.get("handler_exists")
        else "MISSING"
    )

    print(
        "Database Tasks:",
        tasks.get(
            "database_count",
            0
        )
    )

    print(
        "Architecture:",
        tasks.get(
            "architecture_status",
            "UNKNOWN"
        )
    )

    # --------------------------------------------------------
    # KNOWLEDGE
    # --------------------------------------------------------

    knowledge = manifest.get(
        "knowledge",
        {}
    )

    print()
    print("[KNOWLEDGE / MEMORY]")

    for key, value in knowledge.items():

        if isinstance(value, dict):

            print(
                f"  {key}: "
                f"{value.get('status', 'UNKNOWN')}"
            )

        else:

            print(
                f"  {key}: {value}"
            )

    # --------------------------------------------------------
    # OWNERSHIP
    # --------------------------------------------------------

    ownership = manifest.get(
        "ownership",
        {}
    )

    print()
    print("[OWNERSHIP]")

    print(
        "Formal Takeover Layer:",
        ownership.get(
            "formal_takeover_layer"
        )
    )

    print(
        "Formal Knowledge Transfer:",
        ownership.get(
            "formal_knowledge_transfer"
        )
    )

    print(
        "Mission Responsibility:",
        ownership.get(
            "mission_responsibility"
        )
    )

    print(
        "Device Ownership:",
        ownership.get(
            "device_ownership"
        )
    )

    # --------------------------------------------------------
    # VERIFICATION
    # --------------------------------------------------------

    verification = manifest.get(
        "verification",
        {}
    )

    print()
    print("[VERIFICATION]")

    for key, value in verification.items():

        if isinstance(value, dict):

            print(
                f"  {key}: "
                f"{value.get('status', 'UNKNOWN')}"
            )

    # --------------------------------------------------------
    # SYSTEM MEMORY SUMMARY
    # --------------------------------------------------------

    memory_summary = manifest.get(
        "system_memory_summary",
        {}
    )

    print()
    print("[SYSTEM MEMORY SUMMARY]")

    print(
        "Memory Version:",
        memory_summary.get(
            "memory_version"
        )
    )

    print(
        "Milestone:",
        memory_summary.get(
            "milestone"
        )
    )

    print(
        "Next Phase:",
        memory_summary.get(
            "next_phase"
        )
    )

    print(
        "Goal:",
        memory_summary.get(
            "goal"
        )
    )

    # --------------------------------------------------------
    # INTEGRITY
    # --------------------------------------------------------

    integrity = manifest.get(
        "integrity",
        {}
    )

    issues = integrity.get(
        "issues",
        []
    )

    print()
    print("[INTEGRITY]")

    if issues:

        print(
            "⚠️ ISSUES:"
        )

        for issue in issues:
            print(
                " -",
                issue
            )

    else:

        print(
            "✅ NO MANIFEST INTEGRITY ISSUES"
        )

    # --------------------------------------------------------
    # NEXT ACTION
    # --------------------------------------------------------

    print()
    print("[CONTROLLER DECISION]")

    if issues:

        print(
            "⚠️ TAKEOVER BLOCKED BY INTEGRITY ISSUES"
        )

    elif open_items:

        print(
            "🟡 SYSTEM HAS OPEN WORK"
        )

        print(
            "Next action: "
            "inspect and coordinate existing mission work."
        )

    else:

        print(
            "✅ NO OPEN MISSION WORK"
        )

    print()
    print("=" * 80)
    print("READ-ONLY CONTROLLER COMPLETE")
    print("NO FILES MODIFIED")
    print("NO DATABASE RECORDS MODIFIED")
    print("NO AGENTS MODIFIED")
    print("NO MISSIONS MODIFIED")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
