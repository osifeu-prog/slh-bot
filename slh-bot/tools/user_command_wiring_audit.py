#!/usr/bin/env python3

"""
SLH USER COMMAND WIRING AUDIT v1

Read-only static audit.

Purpose:
Determine whether user-facing commands are actually wired
to active runtime handlers.

This tool does NOT:
- start the bot
- restart the bot
- modify runtime state
- import application modules for execution

It only inspects source text.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


COMMANDS = [
    "/start",
    "/help",
    "/join",
    "/register",
    "/user",
    "/progress",
    "/report",
    "/market",
    "/balance",
    "/token",
    "/course",
    "/learn",
    "/ask",
]


EXCLUDED_PARTS = {
    ".git",
    "__pycache__",
    "backups",
    "backup",
    "archives",
    "archive",
    "snapshots",
    "tools",
}


def now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def is_excluded(path: Path):

    return any(
        part in EXCLUDED_PARTS
        for part in path.parts
    )


def scan_python_files():

    files = []

    for path in ROOT.rglob("*.py"):

        if is_excluded(path):
            continue

        files.append(path)

    return files


def classify_path(path: Path):

    relative = str(
        path.relative_to(ROOT)
    )

    parts = set(
        path.relative_to(ROOT).parts
    )

    if path.name == "bot_stable.py":
        return "ACTIVE_ENTRYPOINT"

    if "handlers" in parts:
        return "HANDLER"

    if path.name in {
        "bot.py",
        "bot_core.py",
        "ask_handler.py",
        "advanced_ask_handler.py",
    }:
        return "LEGACY_OR_CORE"

    return "OTHER"


def find_command_mentions(
    command,
    files
):

    pattern = re.compile(
        rf"(?<!\w){re.escape(command)}(?!\w)",
        re.IGNORECASE
    )

    results = []

    for path in files:

        try:

            text = path.read_text(
                encoding="utf-8",
                errors="replace"
            )

        except Exception:

            continue

        if not pattern.search(text):
            continue

        results.append(
            {
                "file": str(
                    path.relative_to(ROOT)
                ),
                "class": classify_path(path),
            }
        )

    return results


def main():

    print("=" * 80)
    print("SLH USER COMMAND WIRING AUDIT v1")
    print("=" * 80)

    files = scan_python_files()

    results = []

    for command in COMMANDS:

        mentions = find_command_mentions(
            command,
            files
        )

        active_entrypoints = [
            item
            for item in mentions
            if item["class"]
            == "ACTIVE_ENTRYPOINT"
        ]

        handlers = [
            item
            for item in mentions
            if item["class"]
            == "HANDLER"
        ]

        legacy = [
            item
            for item in mentions
            if item["class"]
            == "LEGACY_OR_CORE"
        ]

        if active_entrypoints and handlers:

            status = "WIRED_CANDIDATE"

        elif handlers:

            status = "HANDLER_ONLY"

        elif active_entrypoints:

            status = "ENTRYPOINT_ONLY"

        elif legacy:

            status = "LEGACY_OR_CORE_ONLY"

        else:

            status = "NOT_FOUND"

        result = {
            "command": command,
            "status": status,
            "active_entrypoints": active_entrypoints,
            "handlers": handlers,
            "legacy_or_core": legacy,
            "all_mentions": mentions,
        }

        results.append(result)

        if status == "WIRED_CANDIDATE":
            icon = "🟢"

        elif status in {
            "HANDLER_ONLY",
            "ENTRYPOINT_ONLY",
        }:
            icon = "🟡"

        elif status == "LEGACY_OR_CORE_ONLY":
            icon = "⚪"

        else:
            icon = "🔴"

        print()
        print(
            f"{icon} {command}: {status}"
        )

        print(
            "   ACTIVE:",
            len(active_entrypoints)
        )

        print(
            "   HANDLERS:",
            len(handlers)
        )

        print(
            "   LEGACY/CORE:",
            len(legacy)
        )

    report = {
        "audit_version": "1.0",
        "generated_at": now(),
        "total_commands": len(results),
        "results": results,
        "safety": {
            "read_only": True,
            "bot_started": False,
            "restart_performed": False,
            "runtime_state_modified": False,
        },
    }

    output = (
        ROOT
        / "state"
        / "takeover"
        / "user_command_wiring_audit.json"
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    output.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False
        ) + "\n",
        encoding="utf-8"
    )

    print()
    print("=" * 80)
    print("WIRING AUDIT COMPLETE")
    print("=" * 80)

    print()
    print(
        "REPORT:",
        output
    )

    print()
    print("READ-ONLY")
    print("NO BOT START")
    print("NO RESTART")
    print("NO RUNTIME MODIFICATION")


if __name__ == "__main__":
    main()
