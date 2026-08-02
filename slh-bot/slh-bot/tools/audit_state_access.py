#!/usr/bin/env python3

import ast
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent

EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "node_modules",
}

TARGET_FILES = {
    "db.json",
    "agents.json",
}

DIRECT_TERMS = {
    "DB_PATH",
    "SNAPSHOT_PATH",
    "db.json",
    "agents.json",
    "json.load",
    "json.dump",
    "json.loads",
    "json.dumps",
    "open(",
    ".open(",
    ".write(",
    "write_text(",
    "write_bytes(",
    "os.replace(",
}

AUTHORIZED_FILES = {
    "core/agent_state_store.py",
}

TEST_OR_TOOL_PREFIXES = (
    "tools/",
    "tests/",
)

results = []


def classify(path, line, text):
    rel = str(path.relative_to(ROOT))

    if rel in AUTHORIZED_FILES:
        return "AUTHORIZED"

    if rel.startswith(TEST_OR_TOOL_PREFIXES):
        return "TOOL_OR_TEST"

    write_terms = (
        "json.dump",
        "json.dumps",
        ".write(",
        "write_text(",
        "write_bytes(",
        "os.replace(",
    )

    if any(term in text for term in write_terms):
        return "DIRECT_WRITE"

    read_terms = (
        "json.load",
        "json.loads",
        "DB_PATH",
        "SNAPSHOT_PATH",
        "db.json",
        "agents.json",
        "open(",
        ".open(",
    )

    if any(term in text for term in read_terms):
        return "DIRECT_READ"

    return "REFERENCE"


def scan_python(path):
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return

    lines = text.splitlines()

    # Text-level scan
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith("#"):
            continue

        matched = [
            term
            for term in DIRECT_TERMS
            if term in line
        ]

        if matched:
            results.append({
                "file": str(path.relative_to(ROOT)),
                "line": number,
                "type": classify(path, number, line),
                "matches": matched,
                "text": stripped[:240],
            })

    # AST scan for actual direct file opens
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as e:
        results.append({
            "file": str(path.relative_to(ROOT)),
            "line": getattr(e, "lineno", "?"),
            "type": "SYNTAX_ERROR",
            "matches": ["ast.parse"],
            "text": str(e),
        })
        return

    for node in ast.walk(tree):

        if isinstance(node, ast.Call):

            # open(...)
            if isinstance(node.func, ast.Name):
                if node.func.id == "open":
                    results.append({
                        "file": str(path.relative_to(ROOT)),
                        "line": node.lineno,
                        "type": classify(
                            path,
                            node.lineno,
                            "open("
                        ),
                        "matches": ["AST: open()"],
                        "text": "Direct open() call",
                    })

            # Path.open(...)
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == "open":
                    results.append({
                        "file": str(path.relative_to(ROOT)),
                        "line": node.lineno,
                        "type": classify(
                            path,
                            node.lineno,
                            ".open("
                        ),
                        "matches": ["AST: Path.open()"],
                        "text": "Direct Path.open() call",
                    })


def scan_all():

    for path in ROOT.rglob("*.py"):

        if any(
            part in EXCLUDED_DIRS
            for part in path.parts
        ):
            continue

        scan_python(path)


def print_section(title, items):

    print()
    print("=" * 100)
    print(title)
    print("=" * 100)

    if not items:
        print("NONE")
        return

    for item in items:
        print()
        print(
            f"{item['file']}:{item['line']}"
        )
        print(
            f"TYPE    : {item['type']}"
        )
        print(
            f"MATCHES : {', '.join(item['matches'])}"
        )
        print(
            f"CODE    : {item['text']}"
        )


def main():

    print("=" * 100)
    print("SLH STATE ACCESS AUDIT")
    print("=" * 100)

    print()
    print("ROOT:")
    print(ROOT)

    print()
    print("MODE:")
    print("READ-ONLY")
    print("NO FILES MODIFIED")
    print("NO DATABASE MODIFIED")
    print("NO RESTART")

    scan_all()

    # Remove exact duplicate findings
    unique = []
    seen = set()

    for item in results:

        key = (
            item["file"],
            item["line"],
            item["type"],
            tuple(item["matches"]),
        )

        if key not in seen:
            seen.add(key)
            unique.append(item)

    results[:] = unique

    authorized = [
        x for x in results
        if x["type"] == "AUTHORIZED"
    ]

    direct_reads = [
        x for x in results
        if x["type"] == "DIRECT_READ"
    ]

    direct_writes = [
        x for x in results
        if x["type"] == "DIRECT_WRITE"
    ]

    tools_tests = [
        x for x in results
        if x["type"] == "TOOL_OR_TEST"
    ]

    syntax_errors = [
        x for x in results
        if x["type"] == "SYNTAX_ERROR"
    ]

    print()
    print("TOTAL FINDINGS:", len(results))

    print_section(
        "AUTHORIZED STATE ACCESS",
        authorized
    )

    print_section(
        "DIRECT STATE READS",
        direct_reads
    )

    print_section(
        "DIRECT STATE WRITES",
        direct_writes
    )

    print_section(
        "TOOLS / TESTS / AUDIT SCRIPTS",
        tools_tests
    )

    print_section(
        "SYNTAX ERRORS",
        syntax_errors
    )

    # File-level summary
    by_file = defaultdict(list)

    for item in results:
        by_file[item["file"]].append(item)

    print()
    print("=" * 100)
    print("FILE SUMMARY")
    print("=" * 100)

    for file_name in sorted(by_file):

        items = by_file[file_name]

        types = sorted(
            set(
                item["type"]
                for item in items
            )
        )

        print()
        print(file_name)
        print("  Findings:", len(items))
        print("  Types   :", ", ".join(types))

    # Risk assessment
    print()
    print("=" * 100)
    print("ARCHITECTURE RISK ASSESSMENT")
    print("=" * 100)

    if syntax_errors:
        print("🔴 SYNTAX ERRORS FOUND")

    elif direct_writes:
        print("🔴 DIRECT STATE WRITERS FOUND")
        print()
        print(
            "These files may bypass AgentStateStore."
        )

    elif direct_reads:
        print("🟡 DIRECT STATE READERS FOUND")
        print()
        print(
            "Reads may be candidates for migration."
        )

    else:
        print("🟢 NO UNAUTHORIZED DIRECT STATE ACCESS DETECTED")

    print()
    print("=" * 100)
    print("AUTOMATED RECOMMENDATION")
    print("=" * 100)

    if direct_writes:
        print(
            "1. Migrate DIRECT_WRITE files first."
        )
        print(
            "2. Re-run audit."
        )
        print(
            "3. Add runtime State Gateway enforcement."
        )

    elif direct_reads:
        print(
            "1. Review DIRECT_READ files."
        )
        print(
            "2. Migrate important readers to StateStore."
        )
        print(
            "3. Keep tools/tests read-only where appropriate."
        )

    else:
        print(
            "1. AgentStateStore is the single state gateway."
        )
        print(
            "2. Add runtime write protection."
        )
        print(
            "3. Add automatic audit to system health."
        )

    print()
    print("=" * 100)
    print("STATE ACCESS AUDIT COMPLETE")
    print("READ-ONLY")
    print("NO WRITE")
    print("NO RESTART")
    print("=" * 100)


if __name__ == "__main__":
    main()
