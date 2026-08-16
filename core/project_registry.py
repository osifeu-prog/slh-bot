#!/usr/bin/env python3

"""
SLH Project Registry v1

Canonical registry for discovered projects.

Sources:
- state/takeover/termux_project_inventory.json
- state/takeover/project_discovery.json

Read-only with respect to source data.
Writes only the generated registry file.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent

TAKEOVER = ROOT / "state" / "takeover"

INVENTORY_FILE = (
    TAKEOVER / "termux_project_inventory.json"
)

DISCOVERY_FILE = (
    TAKEOVER / "project_discovery.json"
)

REGISTRY_FILE = (
    TAKEOVER / "project_registry.json"
)


def now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def load_json(
    path: Path
) -> dict[str, Any]:

    if not path.exists():
        return {}

    try:

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    return {}


def normalize_project(
    project: dict[str, Any]
) -> dict[str, Any]:

    raw_project_id = (
        project.get("project_id")
        or project.get("name")
        or "unknown"
    )

    raw_name = (
        project.get("name")
        or raw_project_id
        or "unknown"
    )

    raw_path = project.get(
        "path"
    )

    # Canonicalize root discovery entry.
    # The first scanner represents the current project root as ".".
    # It must resolve to the actual project name.
    if raw_project_id in (".", ""):

        project_id = (
            Path(raw_path).name
            if raw_path
            and raw_path not in (".", "")
            else raw_name
        )

    else:

        project_id = raw_project_id

    if project_id in (".", ""):

        project_id = "unknown"

    return {
        "project_id": project_id,
        "name": project.get(
            "name",
            project_id
        ),
        "path": project.get(
            "path"
        ),
        "type": project.get(
            "type",
            "unknown"
        ),
        "status": project.get(
            "status",
            "discovered"
        ),
        "repository": project.get(
            "repository"
        ),
        "deployment": project.get(
            "deployment"
        ),
        "devices": project.get(
            "devices",
            []
        ),
        "installations": project.get(
            "installations",
            []
        ),
        "health": project.get(
            "health",
            "unknown"
        ),
        "git": project.get(
            "git",
            {}
        ),
        "markers": project.get(
            "markers",
            []
        ),
        "last_seen": project.get(
            "last_seen"
        ),
    }


def merge_projects(
    inventory: dict[str, Any],
    discovery: dict[str, Any]
) -> dict[str, dict[str, Any]]:

    projects = {}

    for project in inventory.get(
        "projects",
        []
    ):

        if isinstance(
            project,
            dict
        ):

            normalized = normalize_project(
                project
            )

            projects[
                normalized["project_id"]
            ] = normalized

    for project in discovery.get(
        "projects",
        []
    ):

        if not isinstance(
            project,
            dict
        ):
            continue

        normalized = normalize_project(
            project
        )

        project_id = normalized[
            "project_id"
        ]

        if project_id not in projects:

            projects[
                project_id
            ] = normalized

        else:

            current = projects[
                project_id
            ]

            for key, value in normalized.items():

                if value in (
                    None,
                    {},
                    [],
                    "unknown",
                ):
                    continue

                if current.get(key) in (
                    None,
                    {},
                    [],
                    "unknown",
                ):

                    current[key] = value

    return projects


class ProjectRegistry:

    def __init__(self):

        self.inventory = load_json(
            INVENTORY_FILE
        )

        self.discovery = load_json(
            DISCOVERY_FILE
        )

    def collect(self) -> dict[str, Any]:

        projects = merge_projects(
            self.inventory,
            self.discovery
        )

        return {
            "registry_version": "1.0",
            "generated_at": now(),
            "total": len(projects),
            "projects": projects,
            "sources": {
                "inventory": str(
                    INVENTORY_FILE.relative_to(
                        ROOT
                    )
                ),
                "discovery": str(
                    DISCOVERY_FILE.relative_to(
                        ROOT
                    )
                ),
            },
        }

    def write(self) -> dict[str, Any]:

        registry = self.collect()

        REGISTRY_FILE.write_text(
            json.dumps(
                registry,
                indent=2,
                ensure_ascii=False
            ) + "\n",
            encoding="utf-8"
        )

        return registry


def collect_projects():

    return ProjectRegistry().collect()


if __name__ == "__main__":

    registry = ProjectRegistry().write()

    print("=" * 80)
    print("SLH PROJECT REGISTRY v1")
    print("=" * 80)

    print()
    print(
        "PROJECTS:",
        registry["total"]
    )

    for project_id, project in registry[
        "projects"
    ].items():

        print()
        print(
            "PROJECT:",
            project_id
        )

        print(
            "  TYPE:",
            project["type"]
        )

        print(
            "  PATH:",
            project["path"]
        )

        print(
            "  GIT:",
            project["git"].get(
                "is_repository",
                False
            )
        )

        print(
            "  REMOTE:",
            project["git"].get(
                "remote"
            )
        )

    print()
    print(
        "OUTPUT:",
        REGISTRY_FILE
    )

    print()
    print("=" * 80)
    print("REGISTRY GENERATED")
    print("READ-ONLY SOURCE ACCESS")
    print("NO BOT RESTART")
    print("=" * 80)
