#!/usr/bin/env python3

"""
SLH RUNTIME COMMAND REGISTRATION AUDIT v1

Read-only static audit.

Maps user-facing command registration through the three active paths:

1. Direct decorators in bot_stable.py
2. Dynamic state/custom_handlers loading
3. Modular handlers/loader.py loading

No execution.
No bot start.
No restart.
No runtime modification.
"""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

ENTRYPOINT = ROOT / "bot_stable.py"
LOADER = ROOT / "handlers" / "loader.py"
CUSTOM_DIR = ROOT / "state" / "custom_handlers"


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
    return datetime.now(timezone.utc).isoformat()


def read_tree(path):
    try:
        return ast.parse(
            path.read_text(
                encoding="utf-8",
                errors="replace"
            )
        )
    except Exception:
        return None


def extract_command_decorators(path):
    """
    Detect:
    @bot.message_handler(commands=['x'])
    @bot.message_handler(commands=["x", "y"])
    """

    tree = read_tree(path)

    if tree is None:
        return []

    results = []

    for node in ast.walk(tree):

        if not isinstance(
            node,
            ast.FunctionDef
        ):
            continue

        for decorator in node.decorator_list:

            if not isinstance(
                decorator,
                ast.Call
            ):
                continue

            func = decorator.func

            is_message_handler = (
                isinstance(func, ast.Attribute)
                and func.attr == "message_handler"
            )

            if not is_message_handler:
                continue

            for keyword in decorator.keywords:

                if keyword.arg != "commands":
                    continue

                value = keyword.value

                if isinstance(
                    value,
                    (ast.List, ast.Tuple, ast.Set)
                ):

                    commands = []

                    for item in value.elts:

                        if isinstance(
                            item,
                            ast.Constant
                        ) and isinstance(
                            item.value,
                            str
                        ):

                            command = item.value

                            if not command.startswith("/"):
                                command = "/" + command

                            commands.append(command)

                    results.append(
                        {
                            "commands": commands,
                            "function": node.name,
                            "line": node.lineno,
                        }
                    )

    return results


def extract_register_functions(path):
    """
    Detect register-style functions.
    """

    tree = read_tree(path)

    if tree is None:
        return []

    functions = []

    for node in ast.walk(tree):

        if not isinstance(
            node,
            ast.FunctionDef
        ):
            continue

        name = node.name.lower()

        if (
            name == "register"
            or name.startswith("register_")
            or name in {
                "init",
                "load",
            }
        ):

            functions.append(
                {
                    "function": node.name,
                    "line": node.lineno,
                }
            )

    return functions


def extract_command_mentions(path):
    """
    Detect command strings anywhere in source.
    Used only as supporting evidence.
    """

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="replace"
        )
    except Exception:
        return []

    found = []

    for command in COMMANDS:

        pattern = re.compile(
            rf"(?<!\w){re.escape(command)}(?!\w)",
            re.IGNORECASE
        )

        if pattern.search(text):
            found.append(command)

    return found


def audit_direct_registration():

    results = []

    if not ENTRYPOINT.exists():
        return results

    decorators = extract_command_decorators(
        ENTRYPOINT
    )

    for item in decorators:

        for command in item["commands"]:

            if command in COMMANDS:

                results.append(
                    {
                        "command": command,
                        "path": "DIRECT",
                        "source": str(
                            ENTRYPOINT.relative_to(ROOT)
                        ),
                        "function": item["function"],
                        "line": item["line"],
                        "confidence": "HIGH",
                    }
                )

    return results


def audit_custom_handlers():

    results = []

    if not CUSTOM_DIR.exists():
        return results

    for path in sorted(
        CUSTOM_DIR.glob("*.py")
    ):

        if path.name == "__init__.py":
            continue

        registers = extract_register_functions(
            path
        )

        mentions = extract_command_mentions(
            path
        )

        if not registers:
            continue

        for command in mentions:

            if command in COMMANDS:

                results.append(
                    {
                        "command": command,
                        "path": "DYNAMIC_CUSTOM_HANDLER",
                        "source": str(
                            path.relative_to(ROOT)
                        ),
                        "register_functions": registers,
                        "confidence": "MEDIUM",
                    }
                )

    return results


def extract_loader_modules():

    modules = []

    if not LOADER.exists():
        return modules

    tree = read_tree(LOADER)

    if tree is None:
        return modules

    for node in ast.walk(tree):

        if not isinstance(
            node,
            ast.Constant
        ):
            continue

        if not isinstance(
            node.value,
            str
        ):
            continue

        value = node.value

        if value.startswith(
            "handlers."
        ):

            modules.append(value)

    return sorted(
        set(modules)
    )


def module_to_path(module):

    path = ROOT / Path(
        *module.split(".")
    ).with_suffix(".py")

    if path.exists():
        return path

    return None


def audit_modular_loader():

    results = []

    modules = extract_loader_modules()

    for module in modules:

        path = module_to_path(
            module
        )

        if path is None:
            continue

        registers = extract_register_functions(
            path
        )

        mentions = extract_command_mentions(
            path
        )

        if not registers:
            continue

        for command in mentions:

            if command in COMMANDS:

                results.append(
                    {
                        "command": command,
                        "path": "MODULAR_LOADER",
                        "source": str(
                            path.relative_to(ROOT)
                        ),
                        "module": module,
                        "register_functions": registers,
                        "confidence": "HIGH",
                    }
                )

    return results


def build_command_map(all_results):

    command_map = {}

    for command in COMMANDS:

        entries = [
            item
            for item in all_results
            if item["command"] == command
        ]

        if not entries:

            status = "NOT_REGISTERED"

        elif any(
            item["confidence"] == "HIGH"
            for item in entries
        ):

            status = "REGISTERED_HIGH_CONFIDENCE"

        else:

            status = "REGISTERED_MEDIUM_CONFIDENCE"

        command_map[command] = {
            "status": status,
            "registrations": entries,
        }

    return command_map


def main():

    print("=" * 80)
    print("SLH RUNTIME COMMAND REGISTRATION AUDIT v1")
    print("=" * 80)

    direct = audit_direct_registration()

    custom = audit_custom_handlers()

    modular = audit_modular_loader()

    all_results = (
        direct
        + custom
        + modular
    )

    command_map = build_command_map(
        all_results
    )

    print()
    print("COMMAND REGISTRATION MAP")
    print("=" * 80)

    for command in COMMANDS:

        item = command_map[command]

        status = item["status"]

        if status == "REGISTERED_HIGH_CONFIDENCE":
            icon = "🟢"

        elif status == "REGISTERED_MEDIUM_CONFIDENCE":
            icon = "🟡"

        else:
            icon = "🔴"

        print()
        print(
            f"{icon} {command}: {status}"
        )

        if not item["registrations"]:

            print(
                "   SOURCE: NONE"
            )

            continue

        for registration in item[
            "registrations"
        ]:

            print(
                "   PATH:",
                registration["path"]
            )

            print(
                "   SOURCE:",
                registration["source"]
            )

            if "function" in registration:

                print(
                    "   FUNCTION:",
                    registration["function"]
                )

            if "module" in registration:

                print(
                    "   MODULE:",
                    registration["module"]
                )

            print(
                "   CONFIDENCE:",
                registration["confidence"]
            )

    report = {
        "audit_version": "1.0",
        "generated_at": now(),
        "entrypoint": str(
            ENTRYPOINT.relative_to(ROOT)
        ),
        "loader": str(
            LOADER.relative_to(ROOT)
        ),
        "direct_registrations": direct,
        "dynamic_custom_registrations": custom,
        "modular_loader_registrations": modular,
        "command_map": command_map,
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
        / "runtime_command_registration_audit.json"
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
    print("RUNTIME COMMAND REGISTRATION AUDIT COMPLETE")
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
