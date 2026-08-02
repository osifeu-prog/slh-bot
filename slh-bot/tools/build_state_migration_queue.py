#!/usr/bin/env python3

import json
import re
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent

OUTPUT = (
    ROOT
    / "state"
    / "takeover"
    / "state_migration_queue.json"
)

EXCLUDED_PARTS = {
    ".git",
    "__pycache__",
}

EXCLUDED_DIRS = {
    "state/takeover/backups",
    "state/snapshots",
}

DIRECT_PATTERNS = {
    "DIRECT_READ": [
        r"json\.load",
        r"open\([^)]*db\.json",
        r"open\([^)]*agents\.json",
        r"DB_PATH",
        r"SNAPSHOT_PATH",
    ],
    "DIRECT_WRITE": [
        r"json\.dump",
        r"json\.dumps",
        r"open\([^)]*[\"']w[\"']",
        r"\.write_text",
        r"\.write_bytes",
    ],
}

RUNTIME_PRIORITY = {
    "CRITICAL": [
        "bot_stable.py",
        "state_engine.py",
        "state_manager.py",
        "takeover_controller.py",
        "web/api/app.py",
    ],
    "HIGH": [
        "system_diagnostics.py",
        "system_health.py",
        "subscriptions.py",
        "viewfile_handler.py",
    ],
    "MEDIUM": [
        "core/",
        "handlers/",
        "services/",
    ],
}


def now():
    return datetime.now(timezone.utc).isoformat()


def relative(path):
    return str(path.relative_to(ROOT))


def is_excluded(path):
    rel = relative(path)

    if any(part in EXCLUDED_PARTS for part in path.parts):
        return True

    for excluded in EXCLUDED_DIRS:
        if rel.startswith(excluded):
            return True

    return False


def classify(path):
    rel = relative(path)

    for priority, prefixes in RUNTIME_PRIORITY.items():

        for prefix in prefixes:

            if prefix.endswith("/"):
                if rel.startswith(prefix):
                    return priority

            elif rel == prefix:
                return priority

    if rel.startswith("tests/"):
        return "TEST"

    if rel.startswith("tools/"):
        return "TOOL"

    if rel.startswith("state/takeover/"):
        return "HISTORICAL"

    return "NORMAL"


def scan_file(path):

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="replace"
        )

    except Exception as e:

        return {
            "path": relative(path),
            "classification": classify(path),
            "error": repr(e),
            "findings": [],
        }

    findings = []

    for line_number, line in enumerate(
        text.splitlines(),
        start=1
    ):

        for finding_type, patterns in DIRECT_PATTERNS.items():

            for pattern in patterns:

                if re.search(pattern, line):

                    findings.append(
                        {
                            "type": finding_type,
                            "line": line_number,
                            "code": line.strip(),
                        }
                    )

                    break

    return {
        "path": relative(path),
        "classification": classify(path),
        "findings": findings,
    }


def main():

    print("=" * 80)
    print("SLH STATE MIGRATION QUEUE BUILDER")
    print("=" * 80)

    results = []

    for path in ROOT.rglob("*.py"):

        if is_excluded(path):
            continue

        result = scan_file(path)

        if result["findings"]:
            results.append(result)

    results.sort(
        key=lambda x: (
            {
                "CRITICAL": 0,
                "HIGH": 1,
                "MEDIUM": 2,
                "NORMAL": 3,
                "TEST": 4,
                "TOOL": 5,
                "HISTORICAL": 6,
            }.get(
                x["classification"],
                99
            ),
            x["path"],
        )
    )

    queue = {
        "generated_at": now(),
        "source_of_truth": "core.agent_state_store.AgentStateStore",
        "total_files": len(results),
        "migration_required": [],
        "deferred": [],
    }

    for item in results:

        if item["classification"] in {
            "CRITICAL",
            "HIGH",
            "MEDIUM",
            "NORMAL",
        }:

            queue["migration_required"].append(item)

        else:

            queue["deferred"].append(item)

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        json.dumps(
            queue,
            indent=2,
            ensure_ascii=False
        ) + "\n",
        encoding="utf-8"
    )

    print()
    print("FILES FOUND:", len(results))
    print(
        "RUNTIME MIGRATION QUEUE:",
        len(queue["migration_required"])
    )
    print(
        "DEFERRED:",
        len(queue["deferred"])
    )

    print()
    print("MIGRATION PRIORITY")

    for priority in [
        "CRITICAL",
        "HIGH",
        "MEDIUM",
        "NORMAL",
        "TEST",
        "TOOL",
        "HISTORICAL",
    ]:

        items = [
            x
            for x in results
            if x["classification"] == priority
        ]

        if items:

            print()
            print(
                priority,
                ":",
                len(items)
            )

            for item in items:

                types = sorted(
                    set(
                        f["type"]
                        for f in item["findings"]
                    )
                )

                print(
                    " ",
                    item["path"],
                    "|",
                    ",".join(types)
                )

    print()
    print("QUEUE:")
    print(OUTPUT)

    print()
    print("=" * 80)
    print("READ-ONLY ANALYSIS COMPLETE")
    print("NO FILES MODIFIED")
    print("NO RESTART")
    print("=" * 80)


if __name__ == "__main__":
    main()
