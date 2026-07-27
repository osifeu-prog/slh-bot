#!/usr/bin/env python3

"""
SLH LOADER REGISTRATION AUDIT v1

Read-only static audit.

Analyzes handlers/loader.py and its directly imported modules.

Purpose:
Determine which handlers are:
- imported
- registered
- associated with commands

No execution.
No bot start.
No restart.
No runtime modification.
"""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


LOADER = ROOT / "handlers" / "loader.py"


COMMANDS = {
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
}


def now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def read_tree(path):

    return ast.parse(
        path.read_text(
            encoding="utf-8",
            errors="replace"
        )
    )


def extract_imports(tree):

    imports = []

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Import
        ):

            for alias in node.names:

                imports.append(
                    {
                        "module": alias.name,
                        "name": alias.asname,
                        "type": "import",
                    }
                )

        elif isinstance(
            node,
            ast.ImportFrom
        ):

            module = node.module or ""

            for alias in node.names:

                imports.append(
                    {
                        "module": module,
                        "name": alias.name,
                        "alias": alias.asname,
                        "type": "from_import",
                    }
                )

    return imports


def extract_strings(tree):

    values = []

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Constant
        ) and isinstance(
            node.value,
            str
        ):

            values.append(
                node.value
            )

    return values


def extract_calls(tree):

    calls = []

    for node in ast.walk(tree):

        if not isinstance(
            node,
            ast.Call
        ):

            continue

        function_name = None

        if isinstance(
            node.func,
            ast.Name
        ):

            function_name = node.func.id

        elif isinstance(
            node.func,
            ast.Attribute
        ):

            function_name = node.func.attr

        if function_name:

            calls.append(
                function_name
            )

    return calls


def main():

    print("=" * 80)
    print("SLH LOADER REGISTRATION AUDIT v1")
    print("=" * 80)

    if not LOADER.exists():

        print(
            "❌ handlers/loader.py not found"
        )

        raise SystemExit(1)

    tree = read_tree(
        LOADER
    )

    imports = extract_imports(
        tree
    )

    strings = extract_strings(
        tree
    )

    calls = extract_calls(
        tree
    )

    imported_handlers = []

    for item in imports:

        module = item.get(
            "module",
            ""
        )

        if (
            module.startswith(
                "handlers."
            )
            or module.endswith(
                "_handler"
            )
        ):

            imported_handlers.append(
                item
            )

    registration_calls = [
        call
        for call in calls
        if any(
            keyword in call.lower()
            for keyword in {
                "register",
                "include",
                "attach",
                "add",
                "load",
            }
        )
    ]

    command_mentions = {}

    for command in COMMANDS:

        command_mentions[
            command
        ] = command in strings

    print()
    print(
        "LOADER:",
        LOADER.relative_to(ROOT)
    )

    print()
    print(
        "IMPORTED HANDLER MODULES:",
        len(imported_handlers)
    )

    for item in imported_handlers:

        print(
            "  🟢",
            item
        )

    print()
    print(
        "REGISTRATION-LIKE CALLS:",
        len(registration_calls)
    )

    for call in sorted(
        set(
            registration_calls
        )
    ):

        print(
            "  🔧",
            call
        )

    print()
    print(
        "COMMAND STRINGS IN LOADER:"
    )

    for command, found in (
        command_mentions.items()
    ):

        print(
            "  ",
            "✅" if found else "⚪",
            command
        )

    report = {
        "audit_version": "1.0",
        "generated_at": now(),
        "loader": str(
            LOADER.relative_to(ROOT)
        ),
        "imported_handlers": imported_handlers,
        "registration_calls": sorted(
            set(
                registration_calls
            )
        ),
        "command_mentions": command_mentions,
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
        / "loader_registration_audit.json"
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
    print("LOADER REGISTRATION AUDIT COMPLETE")
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
