#!/usr/bin/env python3

"""
SLH USER ACCEPTANCE AUDIT v1

Read-only audit.
Does not start the bot.
Does not restart anything.
Does not modify runtime state.

Purpose:
Determine whether the current SLH system is ready
to receive real users.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def check(
    name,
    condition,
    detail=""
):
    return {
        "name": name,
        "status": "PASS" if condition else "FAIL",
        "detail": detail,
    }


def main():

    results = []

    # -------------------------------------------------
    # CORE
    # -------------------------------------------------

    bot_file = ROOT / "bot_stable.py"
    db_file = ROOT / "state" / "db.json"

    results.append(
        check(
            "Bot file exists",
            bot_file.exists(),
            str(bot_file)
        )
    )

    results.append(
        check(
            "Database exists",
            db_file.exists(),
            str(db_file)
        )
    )

    # -------------------------------------------------
    # DATABASE
    # -------------------------------------------------

    db = {}

    if db_file.exists():

        try:

            db = json.loads(
                db_file.read_text(
                    encoding="utf-8"
                )
            )

            results.append(
                check(
                    "Database readable",
                    isinstance(db, dict),
                    "JSON object"
                )
            )

        except Exception as exc:

            results.append(
                check(
                    "Database readable",
                    False,
                    str(exc)
                )
            )

    else:

        results.append(
            check(
                "Database readable",
                False,
                "Database missing"
            )
        )

    # -------------------------------------------------
    # USER DATA
    # -------------------------------------------------

    users = db.get(
        "users",
        {}
    )

    results.append(
        check(
            "User storage available",
            isinstance(
                users,
                (dict, list)
            ),
            f"type={type(users).__name__}"
        )
    )

    # -------------------------------------------------
    # PROJECT SYSTEM
    # -------------------------------------------------

    try:

        from core.system_collector import (
            SystemCollector
        )

        snapshot = (
            SystemCollector().collect()
        )

        results.append(
            check(
                "SystemCollector operational",
                isinstance(
                    snapshot,
                    dict
                ),
                "snapshot generated"
            )
        )

        required_sections = {
            "system",
            "health",
            "agents",
            "users",
            "tasks",
            "votes",
            "projects",
            "devices",
            "installations",
            "database",
            "project_graph",
        }

        missing = (
            required_sections
            - set(snapshot.keys())
        )

        results.append(
            check(
                "Unified snapshot contract",
                not missing,
                f"missing={sorted(missing)}"
            )
        )

        graph = snapshot.get(
            "project_graph",
            {}
        )

        results.append(
            check(
                "Project graph available",
                isinstance(
                    graph,
                    dict
                ),
                "graph present"
            )
        )

    except Exception as exc:

        results.append(
            check(
                "SystemCollector operational",
                False,
                str(exc)
            )
        )

    # -------------------------------------------------
    # USER EXPERIENCE FILES
    # -------------------------------------------------

    handlers_dir = ROOT / "handlers"

    results.append(
        check(
            "Handlers directory exists",
            handlers_dir.exists(),
            str(handlers_dir)
        )
    )

    # -------------------------------------------------
    # TEST FILES
    # -------------------------------------------------

    contract_tests = [
        ROOT
        / "tools"
        / "test_system_snapshot_contract.py",

        ROOT
        / "tools"
        / "test_project_registry_contract.py",

        ROOT
        / "tools"
        / "test_project_graph_contract.py",
    ]

    for test_file in contract_tests:

        results.append(
            check(
                f"Contract test: {test_file.name}",
                test_file.exists(),
                str(test_file)
            )
        )

    # -------------------------------------------------
    # DECISION
    # -------------------------------------------------

    failed = [
        result
        for result in results
        if result["status"] == "FAIL"
    ]

    decision = (
        "GO"
        if not failed
        else "NO-GO"
    )

    report = {
        "audit_version": "1.0",
        "generated_at": now(),
        "decision": decision,
        "total_checks": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
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
        / "user_acceptance_audit.json"
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

    print("=" * 80)
    print("SLH USER ACCEPTANCE AUDIT v1")
    print("=" * 80)

    print()

    for result in results:

        icon = (
            "✅"
            if result["status"] == "PASS"
            else "❌"
        )

        print(
            f"{icon} "
            f"{result['status']:4} "
            f"{result['name']}"
        )

        if result["detail"]:

            print(
                f"     {result['detail']}"
            )

    print()
    print("=" * 80)

    if decision == "GO":

        print("🟢 DECISION: GO")
        print("SYSTEM PASSES CURRENT ACCEPTANCE AUDIT")

    else:

        print("🔴 DECISION: NO-GO")
        print(
            f"FAILURES: {len(failed)}"
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
