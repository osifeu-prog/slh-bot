#!/usr/bin/env python3

import ast
import json
import re
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
ENTRYPOINT = ROOT / "bot_stable.py"

OUTPUT = (
    ROOT
    / "state"
    / "takeover"
    / "runtime_state_dependency_map.json"
)

EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    "backups",
    "backup",
    "archives",
    "archive",
    "snapshots",
    "tests",
    "test",
    "tools",
}

EXCLUDED_PREFIXES = {
    "state/takeover/",
}

STATE_GATEWAYS = {
    "core/agent_state_store.py",
    "core/state_gateway.py",
    "core/state_store.py",
}

DIRECT_STATE_PATTERNS = [
    r"state/db\.json",
    r"state/agents\.json",
    r"DB_PATH",
    r"SNAPSHOT_PATH",
    r"json\.load",
    r"json\.dump",
    r"\.write_text",
    r"\.write_bytes",
]


def now():
    return datetime.now(timezone.utc).isoformat()


def rel(path):
    return str(path.relative_to(ROOT))


def excluded(path):

    relative = rel(path)

    if any(
        part in EXCLUDED_DIR_NAMES
        for part in path.parts
    ):
        return True

    for prefix in EXCLUDED_PREFIXES:

        if relative.startswith(prefix):
            return True

    return False


def module_name(path):

    relative = path.relative_to(ROOT)

    parts = list(relative.parts)

    if parts[-1] == "__init__.py":
        parts = parts[:-1]

    else:
        parts[-1] = parts[-1][:-3]

    return ".".join(parts)


def discover_modules():

    modules = {}

    for path in ROOT.rglob("*.py"):

        if excluded(path):
            continue

        try:
            modules[module_name(path)] = path

        except Exception:
            pass

    return modules


def resolve_import(current_module, imported, modules):

    candidates = []

    if imported in modules:
        candidates.append(imported)

    if imported.startswith("."):

        dots = len(imported) - len(
            imported.lstrip(".")
        )

        name = imported.lstrip(".")

        current_parts = current_module.split(".")

        base = current_parts[
            :-dots
        ]

        candidate = ".".join(
            base + ([name] if name else [])
        )

        if candidate in modules:
            candidates.append(candidate)

    return candidates


def extract_imports(path, current_module, modules):

    imports = set()

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

                root = alias.name.split(
                    "."
                )[0]

                matches = [
                    m
                    for m in modules
                    if m == root
                    or m.startswith(
                        root + "."
                    )
                ]

                imports.update(
                    matches
                )

        elif isinstance(
            node,
            ast.ImportFrom
        ):

            if node.module:

                module = node.module

                matches = [
                    m
                    for m in modules
                    if m == module
                    or m.startswith(
                        module + "."
                    )
                ]

                imports.update(
                    matches
                )

    return imports


def state_findings(path):

    try:

        text = path.read_text(
            encoding="utf-8",
            errors="replace"
        )

    except Exception:

        return []

    findings = []

    for line_no, line in enumerate(
        text.splitlines(),
        start=1
    ):

        for pattern in DIRECT_STATE_PATTERNS:

            if re.search(
                pattern,
                line
            ):

                findings.append(
                    {
                        "line": line_no,
                        "pattern": pattern,
                        "code": line.strip(),
                    }
                )

                break

    return findings


def build_dependency_graph():

    modules = discover_modules()

    graph = {}

    for module, path in modules.items():

        graph[module] = {
            "path": rel(path),
            "imports": sorted(
                extract_imports(
                    path,
                    module,
                    modules
                )
            ),
        }

    return graph


def reachable_from_entrypoint(
    graph
):

    entry = module_name(
        ENTRYPOINT
    )

    reachable = set()

    def walk(module):

        if module in reachable:
            return

        reachable.add(module)

        for child in graph.get(
            module,
            {}
        ).get(
            "imports",
            []
        ):

            walk(child)

    if entry in graph:
        walk(entry)

    return reachable


def main():

    print("=" * 80)
    print(
        "SLH RUNTIME STATE DEPENDENCY MAP"
    )
    print("=" * 80)

    if not ENTRYPOINT.exists():

        print(
            "❌ ENTRYPOINT NOT FOUND:",
            ENTRYPOINT
        )

        raise SystemExit(1)

    graph = build_dependency_graph()

    reachable = reachable_from_entrypoint(
        graph
    )

    print()
    print(
        "TOTAL PYTHON MODULES:",
        len(graph)
    )

    print(
        "REACHABLE FROM bot_stable.py:",
        len(reachable)
    )

    runtime = []

    for module in sorted(
        reachable
    ):

        item = graph[module]

        path = ROOT / item["path"]

        findings = state_findings(
            path
        )

        if findings:

            gateway = (
                item["path"]
                in STATE_GATEWAYS
            )

            runtime.append(
                {
                    "module": module,
                    "path": item["path"],
                    "is_gateway": gateway,
                    "findings": findings,
                }
            )

    runtime.sort(
        key=lambda x: (
            not x["is_gateway"],
            x["path"],
        )
    )

    result = {
        "generated_at": now(),
        "entrypoint": "bot_stable.py",
        "total_modules": len(graph),
        "reachable_modules": len(reachable),
        "runtime_state_access": runtime,
        "reachable_modules_list": sorted(
            reachable
        ),
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
        "RUNTIME STATE ACCESS:",
        len(runtime)
    )

    print()
    print(
        "ACTIVE STATE ACCESS MAP"
    )

    for item in runtime:

        label = (
            "STATE GATEWAY"
            if item["is_gateway"]
            else "DIRECT ACCESS"
        )

        print()
        print(
            f"[{label}]",
            item["path"]
        )

        for finding in item[
            "findings"
        ][:5]:

            print(
                " ",
                finding["line"],
                "|",
                finding["code"]
            )

    print()
    print(
        "MAP:",
        OUTPUT
    )

    print()
    print("=" * 80)
    print(
        "RUNTIME ANALYSIS COMPLETE"
    )
    print(
        "READ-ONLY"
    )
    print(
        "NO FILES MODIFIED"
    )
    print(
        "NO RESTART"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()
