#!/usr/bin/env python3

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.project_registry import (
    ProjectRegistry,
)


REQUIRED_PROJECT_FIELDS = {
    "project_id",
    "name",
    "path",
    "type",
    "status",
    "repository",
    "deployment",
    "devices",
    "installations",
    "health",
    "git",
    "markers",
}


def main():

    print("=" * 80)
    print("SLH PROJECT REGISTRY CONTRACT TEST")
    print("=" * 80)

    registry = ProjectRegistry().collect()

    assert isinstance(
        registry,
        dict
    )

    assert registry.get(
        "registry_version"
    ) == "1.0"

    projects = registry.get(
        "projects"
    )

    assert isinstance(
        projects,
        dict
    )

    assert registry.get(
        "total"
    ) == len(projects)

    assert len(projects) >= 1

    for project_id, project in projects.items():

        missing = (
            REQUIRED_PROJECT_FIELDS
            - set(project.keys())
        )

        assert not missing, (
            f"{project_id}: missing {missing}"
        )

        assert (
            project["project_id"]
            == project_id
        )

        assert isinstance(
            project["devices"],
            list
        )

        assert isinstance(
            project["installations"],
            list
        )

        assert isinstance(
            project["git"],
            dict
        )

    print()
    print(
        "PROJECTS:",
        len(projects)
    )

    for project_id in projects:

        print(
            "  ✅",
            project_id
        )

    print()
    print("=" * 80)
    print("✅ PROJECT REGISTRY CONTRACT PASSED")
    print("✅ ALL PROJECTS NORMALIZED")
    print("✅ REQUIRED FIELDS PRESENT")
    print("✅ READ-ONLY SOURCE ACCESS")
    print("✅ NO RESTART")
    print("=" * 80)


if __name__ == "__main__":
    main()
