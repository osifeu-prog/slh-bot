#!/usr/bin/env python3

import json
from datetime import datetime, timezone
from pathlib import Path


HOME = Path.home()

OUTPUT = (
    HOME
    / "slh_clean"
    / "state"
    / "takeover"
    / "termux_project_inventory.json"
)


PROJECT_MARKERS = {
    "bot_stable.py": "telegram_bot",
    "main.py": "python_app",
    "pyproject.toml": "python_project",
    "requirements.txt": "python_project",
    "package.json": "node_project",
    "platformio.ini": "esp32_project",
    "Dockerfile": "docker_project",
    "docker-compose.yml": "docker_project",
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
    ".cache",
}


def now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def is_excluded(path):

    return any(
        part in EXCLUDED_DIRS
        for part in path.parts
    )


def detect_project_type(path):

    markers = []

    for marker in PROJECT_MARKERS:

        if (path / marker).exists():

            markers.append(marker)

    if not markers:
        return None, []

    types = sorted(
        set(
            PROJECT_MARKERS[m]
            for m in markers
        )
    )

    if len(types) == 1:

        return types[0], markers

    return "multi_component", markers


def git_info(path):

    git_dir = path / ".git"

    if not git_dir.exists():

        return {
            "is_repository": False,
            "remote": None,
        }

    remote = None

    config = git_dir / "config"

    if config.exists():

        try:

            text = config.read_text(
                encoding="utf-8",
                errors="replace"
            )

            for line in text.splitlines():

                line = line.strip()

                if line.startswith(
                    "url = "
                ):

                    remote = line[
                        6:
                    ].strip()

                    break

        except Exception:

            pass

    return {
        "is_repository": True,
        "remote": remote,
    }


def scan():

    projects = []

    for path in HOME.iterdir():

        if not path.is_dir():
            continue

        if is_excluded(path):
            continue

        project_type, markers = (
            detect_project_type(path)
        )

        if not project_type:
            continue

        git = git_info(path)

        projects.append(
            {
                "project_id": path.name,
                "name": path.name,
                "path": str(path),
                "type": project_type,
                "markers": markers,
                "git": git,
                "status": "discovered",
                "repository": None,
                "deployment": None,
                "devices": [],
                "installations": [],
                "health": "unknown",
                "last_seen": now(),
            }
        )

    return sorted(
        projects,
        key=lambda x: x["name"].lower()
    )


def main():

    print("=" * 80)
    print("SLH TERMUX PROJECT INVENTORY")
    print("=" * 80)

    projects = scan()

    result = {
        "generated_at": now(),
        "source": "read_only_termux_home_scan",
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
            "  GIT:",
            project["git"]["is_repository"]
        )

        print(
            "  REMOTE:",
            project["git"]["remote"]
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
    print("INVENTORY COMPLETE")
    print("READ-ONLY")
    print("NO RESTART")
    print("=" * 80)


if __name__ == "__main__":
    main()
