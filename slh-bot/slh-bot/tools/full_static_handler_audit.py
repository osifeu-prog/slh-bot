#!/usr/bin/env python3

"""
SLH FULL STATIC HANDLER AUDIT v1

READ-ONLY STATIC ANALYSIS.

Analyzes:

1. bot_stable.py
2. handlers/*.py
3. state/custom_handlers/*.py
4. handlers/loader.py
5. direct imports
6. register/init functions
7. Telegram command decorators
8. dynamic loading paths
9. command ownership
10. duplicate command registrations
11. orphan handlers
12. syntax errors

NO EXECUTION.
NO BOT START.
NO RESTART.
NO RUNTIME MODIFICATION.
"""

from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

ENTRYPOINT = ROOT / "bot_stable.py"
HANDLERS_DIR = ROOT / "handlers"
CUSTOM_DIR = ROOT / "state" / "custom_handlers"
LOADER = HANDLERS_DIR / "loader.py"

OUTPUT = (
    ROOT
    / "state"
    / "takeover"
    / "full_static_handler_audit.json"
)


def now():
    return datetime.now(timezone.utc).isoformat()


def rel(path):
    return str(path.relative_to(ROOT))


def parse_file(path):
    try:
        text = path.read_text(
            encoding="utf-8",
            errors="replace"
        )

        tree = ast.parse(text)

        return {
            "ok": True,
            "tree": tree,
            "error": None,
        }

    except Exception as e:

        return {
            "ok": False,
            "tree": None,
            "error": repr(e),
        }


def get_python_files():

    files = []

    if ENTRYPOINT.exists():
        files.append(ENTRYPOINT)

    if HANDLERS_DIR.exists():
        files.extend(
            sorted(
                HANDLERS_DIR.glob("*.py")
            )
        )

    if CUSTOM_DIR.exists():
        files.extend(
            sorted(
                CUSTOM_DIR.glob("*.py")
            )
        )

    return sorted(
        set(
            path.resolve()
            for path in files
        )
    )


def extract_imports(tree):

    results = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            for alias in node.names:

                results.append(
                    {
                        "type": "import",
                        "module": alias.name,
                        "name": None,
                        "alias": alias.asname,
                        "line": node.lineno,
                    }
                )

        elif isinstance(node, ast.ImportFrom):

            module = node.module or ""

            for alias in node.names:

                results.append(
                    {
                        "type": "from_import",
                        "module": module,
                        "name": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                    }
                )

    return results


def extract_register_functions(tree):

    results = []

    for node in ast.walk(tree):

        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue

        name = node.name.lower()

        if (
            name == "register"
            or name.startswith("register_")
            or name in {
                "init",
                "load",
                "load_handlers",
            }
        ):

            results.append(
                {
                    "function": node.name,
                    "line": node.lineno,
                    "async": isinstance(
                        node,
                        ast.AsyncFunctionDef
                    ),
                    "arguments": [
                        arg.arg
                        for arg in node.args.args
                    ],
                }
            )

    return results


def extract_command_decorators(tree):

    results = []

    for node in ast.walk(tree):

        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue

        for decorator in node.decorator_list:

            if not isinstance(
                decorator,
                ast.Call
            ):
                continue

            func = decorator.func

            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "message_handler"
            ):
                continue

            commands = []

            for keyword in decorator.keywords:

                if keyword.arg != "commands":
                    continue

                value = keyword.value

                if isinstance(
                    value,
                    (ast.List, ast.Tuple, ast.Set)
                ):

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

            if commands:

                results.append(
                    {
                        "commands": commands,
                        "function": node.name,
                        "line": node.lineno,
                    }
                )

    return results


def extract_command_mentions(path):

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="replace"
        )

    except Exception:

        return []

    found = set()

    # Slash command tokens in source.
    matches = re.findall(
        r"(?<![\w])(/[a-zA-Z][a-zA-Z0-9_]{1,40})",
        text
    )

    for command in matches:
        found.add(
            command.lower()
        )

    return sorted(found)


def extract_register_calls(tree):

    results = []

    for node in ast.walk(tree):

        if not isinstance(
            node,
            ast.Call
        ):
            continue

        function = None

        if isinstance(
            node.func,
            ast.Name
        ):

            function = node.func.id

        elif isinstance(
            node.func,
            ast.Attribute
        ):

            function = node.func.attr

        if not function:
            continue

        low = function.lower()

        if (
            "register" in low
            or low in {
                "init",
                "load",
                "load_handlers",
            }
        ):

            results.append(
                {
                    "function": function,
                    "line": node.lineno,
                }
            )

    return results


def classify(path):

    if path == ENTRYPOINT:
        return "ENTRYPOINT"

    if path.parent == HANDLERS_DIR:
        return "HANDLER"

    if path.parent == CUSTOM_DIR:
        return "CUSTOM_HANDLER"

    return "OTHER"


def audit_files():

    results = []

    for path in get_python_files():

        parsed = parse_file(path)

        item = {
            "file": rel(path),
            "class": classify(path),
            "syntax_ok": parsed["ok"],
            "syntax_error": parsed["error"],
            "imports": [],
            "register_functions": [],
            "register_calls": [],
            "decorated_commands": [],
            "command_mentions": [],
        }

        if parsed["ok"]:

            tree = parsed["tree"]

            item["imports"] = extract_imports(tree)

            item["register_functions"] = (
                extract_register_functions(tree)
            )

            item["register_calls"] = (
                extract_register_calls(tree)
            )

            item["decorated_commands"] = (
                extract_command_decorators(tree)
            )

            item["command_mentions"] = (
                extract_command_mentions(path)
            )

        results.append(item)

    return results


def build_command_map(files):

    command_map = defaultdict(list)

    for item in files:

        source = item["file"]

        for decorator in item[
            "decorated_commands"
        ]:

            for command in decorator[
                "commands"
            ]:

                command_map[
                    command
                ].append(
                    {
                        "source": source,
                        "type": "DECORATOR",
                        "function": decorator[
                            "function"
                        ],
                        "line": decorator[
                            "line"
                        ],
                    }
                )

    return dict(
        sorted(
            command_map.items()
        )
    )


def build_registration_map(files):

    registration_map = defaultdict(list)

    for item in files:

        if not item[
            "register_functions"
        ]:

            continue

        registration_map[
            item["file"]
        ].extend(
            item["register_functions"]
        )

    return dict(
        sorted(
            registration_map.items()
        )
    )


def find_loader_references(files):

    references = []

    for item in files:

        for imp in item["imports"]:

            module = imp.get(
                "module",
                ""
            )

            if (
                module.startswith(
                    "handlers."
                )
                or module.startswith(
                    "state.custom_handlers."
                )
            ):

                references.append(
                    {
                        "source": item["file"],
                        "module": module,
                        "line": imp["line"],
                        "type": "IMPORT",
                    }
                )

        for call in item["register_calls"]:

            references.append(
                {
                    "source": item["file"],
                    "function": call["function"],
                    "line": call["line"],
                    "type": "REGISTER_CALL",
                }
            )

    return references


def find_loader_modules():

    modules = []

    if not LOADER.exists():
        return modules

    text = LOADER.read_text(
        encoding="utf-8",
        errors="replace"
    )

    modules = sorted(
        set(
            re.findall(
                r"handlers\.[a-zA-Z0-9_]+",
                text
            )
        )
    )

    return modules


def build_reachability(files):

    reachable = set()

    # Entrypoint itself.
    if ENTRYPOINT.exists():
        reachable.add(
            rel(ENTRYPOINT)
        )

    # Direct imports/references from bot_stable.
    entry = next(
        (
            item
            for item in files
            if item["file"] == "bot_stable.py"
        ),
        None
    )

    if entry:

        for imp in entry["imports"]:

            module = imp.get(
                "module",
                ""
            )

            if module.startswith(
                "handlers."
            ):

                path = (
                    ROOT
                    / Path(
                        *module.split(".")
                    ).with_suffix(".py")
                )

                if path.exists():

                    reachable.add(
                        rel(path)
                    )

    # Modules explicitly listed in loader.
    for module in find_loader_modules():

        path = (
            ROOT
            / Path(
                *module.split(".")
            ).with_suffix(".py")
        )

        if path.exists():

            reachable.add(
                rel(path)
            )

    return sorted(reachable)


def build_duplicate_commands(command_map):

    duplicates = {}

    for command, entries in command_map.items():

        if len(entries) > 1:

            duplicates[command] = entries

    return duplicates


def build_orphans(files, reachable):

    orphans = []

    for item in files:

        if item["class"] not in {
            "HANDLER",
            "CUSTOM_HANDLER",
        }:

            continue

        if item["file"] not in reachable:

            orphans.append(
                item["file"]
            )

    return sorted(orphans)


def main():

    print("=" * 80)
    print("SLH FULL STATIC HANDLER AUDIT v1")
    print("=" * 80)

    files = audit_files()

    command_map = build_command_map(
        files
    )

    registration_map = (
        build_registration_map(
            files
        )
    )

    reachable = build_reachability(
        files
    )

    duplicates = (
        build_duplicate_commands(
            command_map
        )
    )

    orphans = build_orphans(
        files,
        reachable
    )

    syntax_errors = [
        item
        for item in files
        if not item["syntax_ok"]
    ]

    print()
    print(
        "FILES ANALYZED:",
        len(files)
    )

    print(
        "SYNTAX ERRORS:",
        len(syntax_errors)
    )

    print(
        "REACHABLE HANDLER FILES:",
        len(reachable)
    )

    print(
        "COMMANDS FOUND:",
        len(command_map)
    )

    print(
        "DUPLICATE COMMANDS:",
        len(duplicates)
    )

    print(
        "ORPHAN HANDLERS:",
        len(orphans)
    )

    print()
    print("=" * 80)
    print("COMMAND OWNERSHIP")
    print("=" * 80)

    for command in sorted(
        command_map
    ):

        entries = command_map[
            command
        ]

        if len(entries) == 1:
            icon = "🟢"
        else:
            icon = "⚠️"

        print()
        print(
            icon,
            command
        )

        for entry in entries:

            print(
                "   ",
                entry["source"],
                "→",
                entry["function"],
                f"(line {entry['line']})"
            )

    print()
    print("=" * 80)
    print("ORPHAN HANDLERS")
    print("=" * 80)

    if orphans:

        for path in orphans:
            print(
                "👻",
                path
            )

    else:

        print(
            "🟢 NONE"
        )

    print()
    print("=" * 80)
    print("SYNTAX ERRORS")
    print("=" * 80)

    if syntax_errors:

        for item in syntax_errors:

            print(
                "🔴",
                item["file"],
                item["syntax_error"]
            )

    else:

        print(
            "🟢 NONE"
        )

    report = {
        "audit_version": "1.0",
        "generated_at": now(),
        "files": files,
        "command_map": command_map,
        "registration_map": registration_map,
        "loader_modules": find_loader_modules(),
        "reachable_files": reachable,
        "duplicate_commands": duplicates,
        "orphan_handlers": orphans,
        "syntax_errors": syntax_errors,
        "safety": {
            "read_only": True,
            "bot_started": False,
            "restart_performed": False,
            "runtime_state_modified": False,
        },
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False
        ) + "\n",
        encoding="utf-8"
    )

    print()
    print("=" * 80)
    print("FULL STATIC HANDLER AUDIT COMPLETE")
    print("=" * 80)

    print()
    print(
        "REPORT:",
        OUTPUT
    )

    print()
    print("READ-ONLY")
    print("NO BOT START")
    print("NO RESTART")
    print("NO RUNTIME MODIFICATION")


if __name__ == "__main__":
    main()
