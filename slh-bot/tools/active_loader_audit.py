#!/usr/bin/env python3

"""
SLH ACTIVE LOADER AUDIT v1

Read-only static analysis.

Traces:
bot_stable.py
    ↓
imports
    ↓
loader modules
    ↓
handler modules

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


ENTRYPOINT = ROOT / "bot_stable.py"


def now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def module_to_path(module_name):

    relative = Path(
        *module_name.split(".")
    ).with_suffix(".py")

    path = ROOT / relative

    if path.exists():
        return path

    return None


def parse_imports(path):

    imports = []

    try:

        tree = ast.parse(
            path.read_text(
                encoding="utf-8",
                errors="replace"
            )
        )

    except Exception:

        return imports

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Import
        ):

            for alias in node.names:

                imports.append(
                    alias.name
                )

        elif isinstance(
            node,
            ast.ImportFrom
        ):

            if node.module:

                imports.append(
                    node.module
                )

    return imports


def classify(path):

    parts = set(
        path.relative_to(ROOT).parts
    )

    if "handlers" in parts:
        return "HANDLER"

    if path.name in {
        "loader.py",
        "bot_loader.py",
        "handler_loader.py",
    }:
        return "LOADER"

    if path.name == "bot_stable.py":
        return "ENTRYPOINT"

    return "OTHER"


def main():

    print("=" * 80)
    print("SLH ACTIVE LOADER AUDIT v1")
    print("=" * 80)

    if not ENTRYPOINT.exists():

        print("❌ bot_stable.py not found")
        raise SystemExit(1)

    visited = set()
    queue = [ENTRYPOINT]
    discovered = []

    while queue:

        path = queue.pop(0)

        path = path.resolve()

        if path in visited:
            continue

        visited.add(path)

        discovered.append(
            {
                "file": str(
                    path.relative_to(ROOT)
                ),
                "class": classify(path),
            }
        )

        imports = parse_imports(path)

        for module in imports:

            imported_path = (
                module_to_path(module)
            )

            if imported_path:

                queue.append(
                    imported_path
                )

    handlers = [
        item
        for item in discovered
        if item["class"] == "HANDLER"
    ]

    loaders = [
        item
        for item in discovered
        if item["class"] == "LOADER"
    ]

    print()
    print(
        "DISCOVERED FILES:",
        len(discovered)
    )

    print()
    print("LOADERS:")

    if loaders:

        for item in loaders:

            print(
                "  🟢",
                item["file"]
            )

    else:

        print(
            "  ⚪ No loader module discovered"
        )

    print()
    print("HANDLERS REACHABLE FROM bot_stable.py:")

    if handlers:

        for item in handlers:

            print(
                "  🟢",
                item["file"]
            )

    else:

        print(
            "  🔴 NONE"
        )

    report = {
        "audit_version": "1.0",
        "generated_at": now(),
        "entrypoint": "bot_stable.py",
        "discovered": discovered,
        "loaders": loaders,
        "handlers": handlers,
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
        / "active_loader_audit.json"
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
    print("ACTIVE LOADER AUDIT COMPLETE")
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
