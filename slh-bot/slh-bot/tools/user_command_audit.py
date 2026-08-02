#!/usr/bin/env python3

"""
SLH USER COMMAND AUDIT v1

Read-only source audit.

Purpose:
Map the actual user-facing command surface
without starting or restarting the bot.

No runtime modification.
No bot start.
No restart.
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


def now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def scan_python_files():

    files = []

    for path in ROOT.rglob("*.py"):

        if any(
            part in {
                ".git",
                "__pycache__",
                "backups",
                "backup",
                "archives",
                "archive",
            }
            for part in path.parts
        ):
            continue

        files.append(path)

    return files


def audit_command(
    command,
    files
):

    pattern = re.compile(
        rf"(?<!\w){re.escape(command)}(?!\w)",
        re.IGNORECASE
    )

    matches = []

    for path in files:

        try:

            text = path.read_text(
                encoding="utf-8",
                errors="replace"
            )

        except Exception:

            continue

        if pattern.search(text):

            matches.append(
                str(
                    path.relative_to(ROOT)
                )
            )

    return matches


def main():

    print("=" * 80)
    print("SLH USER COMMAND AUDIT v1")
    print("=" * 80)

    files = scan_python_files()

    results = []

    for command in COMMANDS:

        matches = audit_command(
            command,
            files
        )

        status = (
            "FOUND"
            if matches
            else "MISSING"
        )

        results.append(
            {
                "command": command,
                "status": status,
                "files": matches,
            }
        )

        icon = (
            "✅"
            if matches
            else "❌"
        )

        print()
        print(
            f"{icon} {command}"
        )

        if matches:

            for match in matches:

                print(
                    f"   {match}"
                )

        else:

            print(
                "   NOT FOUND"
            )

    found = [
        item
        for item in results
        if item["status"] == "FOUND"
    ]

    missing = [
        item
        for item in results
        if item["status"] == "MISSING"
    ]

    report = {
        "audit_version": "1.0",
        "generated_at": now(),
        "total_commands": len(results),
        "found": len(found),
        "missing": len(missing),
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
        / "user_command_audit.json"
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
    print(
        "FOUND:",
        len(found)
    )

    print(
        "MISSING:",
        len(missing)
    )

    print(
        "TOTAL:",
        len(results)
    )

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
