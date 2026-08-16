#!/usr/bin/env python3

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.system_collector import (
    SystemCollector,
)


REQUIRED_SECTIONS = {
    "snapshot_version",
    "collected_at",
    "system",
    "health",
    "agents",
    "users",
    "tasks",
    "votes",
    "projects",
    "devices",
    "installations",
    "database",
    "sources",
}


def main():

    print("=" * 80)
    print("SLH SYSTEM SNAPSHOT CONTRACT TEST")
    print("=" * 80)

    snapshot = SystemCollector().collect()

    assert isinstance(
        snapshot,
        dict
    )

    missing = (
        REQUIRED_SECTIONS
        - set(snapshot.keys())
    )

    assert not missing, (
        f"Missing sections: {missing}"
    )

    assert isinstance(
        snapshot["system"],
        dict
    )

    assert isinstance(
        snapshot["health"],
        dict
    )

    assert isinstance(
        snapshot["agents"],
        dict
    )

    assert isinstance(
        snapshot["users"],
        dict
    )

    assert isinstance(
        snapshot["tasks"],
        dict
    )

    assert isinstance(
        snapshot["votes"],
        dict
    )

    assert isinstance(
        snapshot["projects"],
        dict
    )

    assert isinstance(
        snapshot["devices"],
        dict
    )

    assert isinstance(
        snapshot["installations"],
        dict
    )

    assert isinstance(
        snapshot["database"],
        dict
    )

    assert isinstance(
        snapshot["sources"],
        dict
    )

    print()
    print("Required sections:")
    print(
        "  ",
        ", ".join(
            sorted(REQUIRED_SECTIONS)
        )
    )

    print()
    print("Snapshot version:")
    print(
        "  ",
        snapshot["snapshot_version"]
    )

    print()
    print("Health:")
    print(
        "  ",
        snapshot["health"]
    )

    print()
    print("=" * 80)
    print("✅ SNAPSHOT CONTRACT PASSED")
    print("✅ ALL REQUIRED SECTIONS PRESENT")
    print("✅ STRUCTURE VALID")
    print("✅ READ-ONLY")
    print("✅ NO RESTART")
    print("=" * 80)


if __name__ == "__main__":
    main()
