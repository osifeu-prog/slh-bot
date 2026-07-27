#!/usr/bin/env python3

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

OUTPUT = (
    ROOT
    / "state"
    / "takeover"
    / "project_discovery.json"
)


PROJECT_MARKERS = {
    "bot_stable.py": "telegram_bot",
    "main.py": "python_app",
    "pyproject.toml": "python_project",
    "requirements.txt": "python_project",
    "package.json": "node_project",
    "platformio.ini": "esp32_project",
    "docker-compose.yml": "docker_project",
    "Dockerfile": "docker_project",
    "Cargo.toml": "rust_project",
}


EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "backups",
    "backup",
    "archives",
    "archive",
    "snapshots",
}


def now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def relative(path):
    return str(
        path.relative_to(ROOT)
    )


def detect_type(path):
    detected = set()

    for marker, project_type in PROJECT_MARKERS.items():

        if (path / marker).exists():
            detected.add(project_type)

    if not detected:
        return None

    if len(detected) == 1:
        return next(iter(detected))

    return "multi_component"


def scan_directory(path):

    if any(
        part in EXCLUDED_DIRS
        for part in path.parts
    ):
        return None

    project_type = detect_type(path)

    if not project_type:
        return None

    project_id = (
        relative(path)
        .replace("/", "_")
        .replace("\\", "_")
        or "root"
    )

    return {
        "project_id": project_id,
        "name": path.name or "slh_clean",
        "path": relative(path),
        "type": project_type,
        "status": "discovered",
        "repository": None,
        "deployment": None,
        "devices": [],
        "installations": [],
        "health": "unknown",
        "last_seen": now(),
        "markers": [
            marker
            for marker in PROJECT_MARKERS
            if (path / marker).exists()
        ],
    }


def main():

    print("=" * 80)
    print("SLH PROJECT DISCOVERY")
    print("=" * 80)

    projects = []

    candidates = [
        ROOT,
        *ROOT.iterdir(),
    ]

    seen = set()

    for path in candidates:

        if not path.is_dir():
            continue

        resolved = path.resolve()

        if resolved in seen:
            continue

        seen.add(resolved)

        project = scan_directory(path)

        if project:
            projects.append(project)

    result = {
        "generated_at": now(),
        "source": "read_only_filesystem_scan",
        "total": len(projects),
        "projects": projects,
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        ) + "\n",
        encoding="utf-8"
    )

    print()
    print(
        "PROJECTS DISCOVERED:",
        len(projects)
    )

    for project in projects:

        print()
        print(
            "PROJECT:",
            project["name"]
        )

        print(
            "  PATH:",
            project["path"]
        )

        print(
            "  TYPE:",
            project["type"]
        )

        print(
            "  MARKERS:",
            ", ".join(
                project["markers"]
            )
        )

    print()
    print(
        "OUTPUT:",
        OUTPUT
    )

    print()
    print("=" * 80)
    print("DISCOVERY COMPLETE")
    print("READ-ONLY")
    print("NO RESTART")
    print("=" * 80)


if __name__ == "__main__":
    main()
