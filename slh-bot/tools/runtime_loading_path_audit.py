#!/usr/bin/env python3

"""
SLH RUNTIME LOADING PATH AUDIT v1

READ-ONLY STATIC ANALYSIS.

Traces the real code paths that may load handlers:

1. bot_stable.py
2. handlers.loader
3. load_handlers(...)
4. dynamic imports
5. importlib usage
6. custom handler loading
7. register(...) calls
8. direct handler imports
9. duplicate loading paths
10. handlers with commands but no detected loading path

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
LOADER = ROOT / "handlers" / "loader.py"
HANDLERS_DIR = ROOT / "handlers"
CUSTOM_DIR = ROOT / "state" / "custom_handlers"

OUTPUT = (
    ROOT
    / "state"
    / "takeover"
    / "runtime_loading_path_audit.json"
)


def now():
    return datetime.now(timezone.utc).isoformat()


def rel(path):
    return str(path.relative_to(ROOT))


def parse(path):
    try:
        text = path.read_text(
            encoding="utf-8",
            errors="replace"
        )

        return {
            "ok": True,
            "tree": ast.parse(text),
            "text": text,
            "error": None,
        }

    except Exception as e:

        return {
            "ok": False,
            "tree": None,
            "text": "",
            "error": repr(e),
        }


def all_python_files():

    files = []

    if ENTRYPOINT.exists():
        files.append(ENTRYPOINT)

    if HANDLERS_DIR.exists():
        files.extend(
            HANDLERS_DIR.glob("*.py")
        )

    if CUSTOM_DIR.exists():
        files.extend(
            CUSTOM_DIR.glob("*.py")
        )

    return sorted(
        set(
            p.resolve()
            for p in files
        )
    )


def extract_imports(tree):

    results = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            for alias in node.names:

                results.append({
                    "type": "import",
                    "module": alias.name,
                    "name": None,
                    "line": node.lineno,
                })

        elif isinstance(node, ast.ImportFrom):

            results.append({
                "type": "from_import",
                "module": node.module or "",
                "name": "*"
                if any(
                    a.name == "*"
                    for a in node.names
                )
                else [
                    a.name
                    for a in node.names
                ],
                "line": node.lineno,
            })

    return results


def extract_calls(tree):

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
            "load" in low
            or "register" in low
            or "import" in low
            or low in {
                "init",
                "exec",
            }
        ):

            results.append({
                "function": function,
                "line": node.lineno,
            })

    return results


def extract_dynamic_loading(tree, text):

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

        if function in {
            "import_module",
            "reload",
        }:

            results.append({
                "function": function,
                "line": node.lineno,
                "type": "DYNAMIC_IMPORT",
            })

    for match in re.finditer(
        r"importlib\.[A-Za-z_]+",
        text
    ):

        results.append({
            "function": match.group(0),
            "line": text[:match.start()].count("\n") + 1,
            "type": "IMPORTLIB",
        })

    for match in re.finditer(
        r"__import__\s*\(",
        text
    ):

        results.append({
            "function": "__import__",
            "line": text[:match.start()].count("\n") + 1,
            "type": "BUILTIN_DYNAMIC_IMPORT",
        })

    return results


def extract_function_calls(tree, names):

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

        if function in names:

            results.append({
                "function": function,
                "line": node.lineno,
            })

    return results


def extract_registered_commands(tree):

    results = []

    for node in ast.walk(tree):

        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            )
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
                isinstance(
                    func,
                    ast.Attribute
                )
                and func.attr == "message_handler"
            ):

                continue

            for keyword in decorator.keywords:

                if keyword.arg != "commands":
                    continue

                value = keyword.value

                if isinstance(
                    value,
                    (
                        ast.List,
                        ast.Tuple,
                        ast.Set,
                    )
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

                            if not command.startswith(
                                "/"
                            ):

                                command = "/" + command

                            results.append({
                                "command": command.lower(),
                                "function": node.name,
                                "line": node.lineno,
                            })

    return results


def inspect_file(path):

    parsed = parse(path)

    result = {
        "file": rel(path),
        "syntax_ok": parsed["ok"],
        "syntax_error": parsed["error"],
        "imports": [],
        "load_calls": [],
        "register_calls": [],
        "dynamic_loading": [],
        "registered_commands": [],
    }

    if not parsed["ok"]:
        return result

    tree = parsed["tree"]

    result["imports"] = extract_imports(tree)

    result["load_calls"] = (
        extract_function_calls(
            tree,
            {
                "load",
                "load_handlers",
                "load_module",
                "load_plugins",
                "load_custom_handlers",
            }
        )
    )

    result["register_calls"] = (
        extract_function_calls(
            tree,
            {
                "register",
                "register_handler",
                "register_handlers",
                "register_ask_handler",
            }
        )
    )

    result["dynamic_loading"] = (
        extract_dynamic_loading(
            tree,
            parsed["text"]
        )
    )

    result["registered_commands"] = (
        extract_registered_commands(
            tree
        )
    )

    return result


def module_path(module):

    path = (
        ROOT
        / Path(
            *module.split(".")
        ).with_suffix(".py")
    )

    if path.exists():
        return path

    return None


def loader_modules():

    if not LOADER.exists():
        return []

    parsed = parse(LOADER)

    if not parsed["ok"]:
        return []

    modules = set()

    for node in ast.walk(
        parsed["tree"]
    ):

        if isinstance(
            node,
            ast.Constant
        ) and isinstance(
            node.value,
            str
        ):

            value = node.value

            if (
                value.startswith(
                    "handlers."
                )
                or value.startswith(
                    "state.custom_handlers."
                )
            ):

                modules.add(value)

    return sorted(modules)


def find_direct_entrypoint_modules():

    if not ENTRYPOINT.exists():
        return []

    parsed = parse(ENTRYPOINT)

    if not parsed["ok"]:
        return []

    modules = set()

    for imp in extract_imports(
        parsed["tree"]
    ):

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

            modules.add(module)

    return sorted(modules)


def build_loading_graph():

    graph = {
        "entrypoint": rel(ENTRYPOINT)
        if ENTRYPOINT.exists()
        else None,
        "loader": rel(LOADER)
        if LOADER.exists()
        else None,
        "direct_entrypoint_modules": (
            find_direct_entrypoint_modules()
        ),
        "loader_modules": loader_modules(),
        "dynamic_import_paths": [],
        "custom_handler_paths": [],
    }

    for path in all_python_files():

        parsed = parse(path)

        if not parsed["ok"]:
            continue

        dynamic = extract_dynamic_loading(
            parsed["tree"],
            parsed["text"]
        )

        if dynamic:

            graph[
                "dynamic_import_paths"
            ].append({
                "source": rel(path),
                "events": dynamic,
            })

        text = parsed["text"]

        if (
            "custom_handlers"
            in text
            or "state/custom_handlers"
            in text
            or "state.custom_handlers"
            in text
        ):

            graph[
                "custom_handler_paths"
            ].append({
                "source": rel(path),
            })

    return graph


def build_handler_status(inspections):

    status = []

    direct_modules = set(
        find_direct_entrypoint_modules()
    )

    loaded_modules = set(
        loader_modules()
    )

    for item in inspections:

        path = item["file"]

        if path == "bot_stable.py":
            continue

        if (
            not path.startswith(
                "handlers/"
            )
            and not path.startswith(
                "state/custom_handlers/"
            )
        ):

            continue

        module = path[:-3].replace(
            "/",
            "."
        )

        reasons = []

        if module in direct_modules:
            reasons.append(
                "DIRECT_ENTRYPOINT_IMPORT"
            )

        if module in loaded_modules:
            reasons.append(
                "LOADER_MODULE"
            )

        if item[
            "registered_commands"
        ]:

            reasons.append(
                "HAS_COMMAND_DECORATORS"
            )

        if item[
            "register_calls"
        ]:

            reasons.append(
                "HAS_REGISTER_CALLS"
            )

        if item[
            "dynamic_loading"
        ]:

            reasons.append(
                "HAS_DYNAMIC_LOADING"
            )

        status.append({
            "file": path,
            "module": module,
            "commands": item[
                "registered_commands"
            ],
            "reasons": reasons,
            "directly_referenced": (
                module in direct_modules
            ),
            "listed_in_loader": (
                module in loaded_modules
            ),
            "loading_evidence": bool(
                reasons
            ),
        })

    return status


def main():

    print("=" * 80)
    print(
        "SLH RUNTIME LOADING PATH AUDIT v1"
    )
    print("=" * 80)

    inspections = []

    for path in all_python_files():

        inspections.append(
            inspect_file(path)
        )

    graph = build_loading_graph()

    handler_status = (
        build_handler_status(
            inspections
        )
    )

    syntax_errors = [
        item
        for item in inspections
        if not item["syntax_ok"]
    ]

    dynamic_paths = (
        graph[
            "dynamic_import_paths"
        ]
    )

    custom_paths = (
        graph[
            "custom_handler_paths"
        ]
    )

    print()
    print(
        "FILES ANALYZED:",
        len(inspections)
    )

    print(
        "SYNTAX ERRORS:",
        len(syntax_errors)
    )

    print(
        "DIRECT ENTRYPOINT MODULES:",
        len(
            graph[
                "direct_entrypoint_modules"
            ]
        )
    )

    print(
        "LOADER MODULES:",
        len(
            graph[
                "loader_modules"
            ]
        )
    )

    print(
        "DYNAMIC LOADING PATHS:",
        len(dynamic_paths)
    )

    print(
        "CUSTOM HANDLER REFERENCES:",
        len(custom_paths)
    )

    print()
    print("=" * 80)
    print("ENTRYPOINT → LOADER PATH")
    print("=" * 80)

    print()

    if ENTRYPOINT.exists():

        print(
            "🟢 ENTRYPOINT:",
            rel(ENTRYPOINT)
        )

    else:

        print(
            "🔴 ENTRYPOINT MISSING"
        )

    print()

    print(
        "DIRECT IMPORTS:"
    )

    for module in graph[
        "direct_entrypoint_modules"
    ]:

        print(
            "   →",
            module
        )

    print()

    print(
        "LOADER MODULES:"
    )

    for module in graph[
        "loader_modules"
    ]:

        print(
            "   →",
            module
        )

    print()
    print("=" * 80)
    print("DYNAMIC LOADING")
    print("=" * 80)

    if dynamic_paths:

        for item in dynamic_paths:

            print()
            print(
                "📦",
                item["source"]
            )

            for event in item[
                "events"
            ]:

                print(
                    "   →",
                    event["function"],
                    f"(line {event['line']})"
                )

    else:

        print(
            "🟡 NONE DETECTED"
        )

    print()
    print("=" * 80)
    print("CUSTOM HANDLER LOADING EVIDENCE")
    print("=" * 80)

    if custom_paths:

        for item in custom_paths:

            print(
                "📦",
                item["source"]
            )

    else:

        print(
            "🔴 NONE DETECTED"
        )

    print()
    print("=" * 80)
    print("HANDLER LOADING STATUS")
    print("=" * 80)

    for item in handler_status:

        if (
            item["directly_referenced"]
            or item["listed_in_loader"]
        ):

            icon = "🟢"

        elif item[
            "loading_evidence"
        ]:

            icon = "🟡"

        else:

            icon = "🔴"

        print()
        print(
            icon,
            item["file"]
        )

        print(
            "   MODULE:",
            item["module"]
        )

        print(
            "   DIRECT:",
            item[
                "directly_referenced"
            ]
        )

        print(
            "   LOADER:",
            item[
                "listed_in_loader"
            ]
        )

        if item["commands"]:

            print(
                "   COMMANDS:",
                ", ".join(
                    x["command"]
                    for x in item[
                        "commands"
                    ]
                )
            )

        if item["reasons"]:

            print(
                "   EVIDENCE:",
                ", ".join(
                    item["reasons"]
                )
            )

    report = {
        "audit_version": "1.0",
        "generated_at": now(),
        "entrypoint": rel(ENTRYPOINT)
        if ENTRYPOINT.exists()
        else None,
        "loader": rel(LOADER)
        if LOADER.exists()
        else None,
        "files": inspections,
        "loading_graph": graph,
        "handler_status": handler_status,
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
    print(
        "RUNTIME LOADING PATH AUDIT COMPLETE"
    )
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
