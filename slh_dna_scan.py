from pathlib import Path
import ast
import json
import hashlib
import os
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_slh_map"

OUT.mkdir(exist_ok=True)

EXCLUDED_DIRS = {
    "venv",
    ".venv",
    "__pycache__",
    ".git",
    "tests",
    "_archive",
    "archive",
    "node_modules",
    "_slh_map",
}

ENTRYPOINT_FILENAMES = {
    "SLH_MAIN.py",
    "SLH_KERNEL.py",
    "SLH_GATEWAY.py",
    "SLH_BOT_ADAPTER.py",
    "bot_stable.py",
    "bot_gateway.py",
    "slh.py",
    "webapp.py",
}

EXCLUDED_FILES = {
    "system_map.json",
    "summary.json",
}


def excluded_file(name):
    n = name.lower()

    return (
        "backup" in n
        or "recovery" in n
        or "copy" in n
        or n.endswith(".bak")
        or n.endswith(".old")
    )


def should_exclude_dir(name):
    return (
        name in EXCLUDED_DIRS
        or name.startswith("_BACKUP_")
    )


def collect_python_files():
    files = []

    for dirpath, dirnames, filenames in os.walk(ROOT):

        dirnames[:] = [
            d
            for d in dirnames
            if not should_exclude_dir(d)
        ]

        current = Path(dirpath)

        for filename in filenames:

            if not filename.endswith(".py"):
                continue

            if filename in EXCLUDED_FILES:
                continue

            if excluded_file(filename):
                continue

            path = current / filename

            try:
                rel = path.relative_to(ROOT)
            except Exception:
                continue

            if "_slh_map" in rel.parts:
                continue

            files.append(path)

    return sorted(
        files,
        key=lambda p: str(p).lower()
    )


def relative_path(path):
    return str(
        path.relative_to(ROOT)
    ).replace("\\", "/")


def module_name(path):
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)

    if parts and parts[-1] == "__init__":
        parts = parts[:-1]

    return ".".join(parts)


def safe_source(path):
    try:
        raw = path.read_bytes()

        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]

        return raw.decode("utf-8")

    except UnicodeDecodeError:
        try:
            return path.read_text(
                encoding="utf-8-sig",
                errors="replace",
            )
        except Exception:
            return ""

    except Exception:
        return ""


def dotted_name(node):
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        base = dotted_name(node.value)

        if base:
            return f"{base}.{node.attr}"

        return node.attr

    return None


def scan():
    nodes = []
    edges = []

    py_files = collect_python_files()

    print(f"Scanning Python files: {len(py_files)}")

    for index, path in enumerate(py_files, 1):

        if index % 50 == 0:
            print(
                f"  scanned {index}/{len(py_files)}"
            )

        source = safe_source(path)

        try:
            tree = ast.parse(
                source,
                filename=str(path),
            )
            parse_error = None

        except SyntaxError as e:
            tree = None
            parse_error = str(e)

        rel = relative_path(path)
        mod = module_name(path)

        try:
            stat = path.stat()
            size = stat.st_size
            mtime = datetime.fromtimestamp(
                stat.st_mtime,
                tz=timezone.utc,
            ).isoformat()

        except Exception:
            size = 0
            mtime = None

        node = {
            "id": hashlib.sha1(
                rel.encode("utf-8")
            ).hexdigest()[:12],

            "path": rel,
            "module": mod,
            "size": size,
            "mtime": mtime,

            "imports": [],
            "functions": [],
            "classes": [],
            "commands": [],
            "state_reads": [],
            "state_writes": [],
            "calls": [],
            "entrypoint_signals": [],

            "parse_error": parse_error,
        }

        if tree is not None:

            for n in ast.walk(tree):

                if isinstance(
                    n,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    ),
                ):
                    node["functions"].append(n.name)

                    if n.name in {
                        "main",
                        "run",
                        "start",
                        "startup",
                        "bootstrap",
                        "handle",
                        "execute",
                        "dispatch",
                    }:
                        node[
                            "entrypoint_signals"
                        ].append(
                            f"function:{n.name}"
                        )

                elif isinstance(n, ast.ClassDef):
                    node["classes"].append(n.name)

                elif isinstance(n, ast.Import):

                    for alias in n.names:
                        node["imports"].append(
                            alias.name
                        )

                elif isinstance(n, ast.ImportFrom):

                    base = n.module or ""

                    for alias in n.names:
                        node["imports"].append(
                            f"{base}.{alias.name}".strip(".")
                        )

                elif isinstance(n, ast.Call):

                    name = dotted_name(n.func)

                    if not name:
                        continue

                    node["calls"].append(name)

                    lower = name.lower()

                    if any(
                        x in lower
                        for x in [
                            "register_command",
                            "add_handler",
                            "register_handler",
                            "router",
                            "command",
                        ]
                    ):
                        node["commands"].append(name)

                    if any(
                        x in lower
                        for x in [
                            "state.get",
                            "state.read",
                            "load_state",
                            "get_state",
                            "read_state",
                            "fetch_state",
                        ]
                    ):
                        node["state_reads"].append(name)

                    if any(
                        x in lower
                        for x in [
                            "state.set",
                            "state.write",
                            "save_state",
                            "set_state",
                            "write_state",
                            "update_state",
                        ]
                    ):
                        node["state_writes"].append(name)

        if path.name in ENTRYPOINT_FILENAMES:
            node["entrypoint_signals"].append(
                f"filename:{path.name}"
            )

        if "handler" in path.name.lower():
            node["entrypoint_signals"].append(
                "handler_filename"
            )

        nodes.append(node)

    module_lookup = {
        n["module"]: n
        for n in nodes
    }

    for n in nodes:

        source_mod = n["module"]

        for imp in n["imports"]:

            target = None

            if imp in module_lookup:
                target = imp

            else:

                candidates = [
                    m
                    for m in module_lookup
                    if (
                        imp.startswith(m + ".")
                        or m.startswith(imp + ".")
                    )
                ]

                if candidates:
                    target = sorted(
                        candidates,
                        key=len,
                        reverse=True,
                    )[0]

            if target and target != source_mod:

                edges.append({
                    "source": source_mod,
                    "target": target,
                    "type": "IMPORTS",
                })

    seen = set()
    unique_edges = []

    for edge in edges:

        key = (
            edge["source"],
            edge["target"],
            edge["type"],
        )

        if key in seen:
            continue

        seen.add(key)
        unique_edges.append(edge)

    edges = unique_edges

    generated = datetime.now(
        timezone.utc
    ).isoformat()

    snapshot = {
        "schema": "slh-system-map/v2",
        "generated_at": generated,
        "root": str(ROOT),
        "file_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }

    system_map = OUT / "system_map.json"
    summary_file = OUT / "summary.json"

    system_map.write_text(
        json.dumps(
            snapshot,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = {
        "schema": "slh-system-map-summary/v2",
        "generated_at": generated,
        "files": len(nodes),
        "edges": len(edges),

        "parse_errors": sum(
            1
            for n in nodes
            if n["parse_error"]
        ),

        "entrypoint_candidates": sum(
            1
            for n in nodes
            if n["entrypoint_signals"]
        ),

        "command_candidates": sum(
            1
            for n in nodes
            if n["commands"]
        ),

        "state_read_candidates": sum(
            1
            for n in nodes
            if n["state_reads"]
        ),

        "state_write_candidates": sum(
            1
            for n in nodes
            if n["state_writes"]
        ),
    }

    summary_file.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("========================================")
    print("        SLH OS DNA MAP")
    print("========================================")
    print(f"Python files : {summary['files']}")
    print(f"Import edges : {summary['edges']}")
    print(f"Parse errors : {summary['parse_errors']}")
    print(
        f"Entrypoints  : "
        f"{summary['entrypoint_candidates']}"
    )
    print(
        f"Commands     : "
        f"{summary['command_candidates']}"
    )
    print(
        f"State reads  : "
        f"{summary['state_read_candidates']}"
    )
    print(
        f"State writes : "
        f"{summary['state_write_candidates']}"
    )
    print()
    print(f"MAP:     {system_map}")
    print(f"SUMMARY: {summary_file}")
    print("========================================")

    return snapshot, summary


if __name__ == "__main__":
    scan()
