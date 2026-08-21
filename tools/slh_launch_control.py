#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime, timezone
import json
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
PLAN_FILE = ROOT / "LAUNCH_PLAN.json"


def load_plan():
    if not PLAN_FILE.exists():
        raise SystemExit("BLOCKED: LAUNCH_PLAN.json missing")

    return json.loads(
        PLAN_FILE.read_text(encoding="utf-8")
    )


def git_value(args):
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unknown"


def git_state():
    head = git_value(["rev-parse", "HEAD"])
    origin = git_value(["rev-parse", "origin/main"])

    try:
        status = subprocess.check_output(
            ["git", "status", "--short"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL
        ).splitlines()
    except Exception:
        status = []

    return {
        "head": head,
        "origin_main": origin,
        "synced": head == origin,
        "worktree_clean": len(status) == 0,
        "uncommitted_files": status,
    }


def gate_weight(gate):
    return float(gate.get("estimate_hours", 0))


def calculate(plan):
    gates = plan["gates"]

    total_hours = sum(
        gate_weight(g)
        for g in gates
    )

    completed_hours = sum(
        gate_weight(g)
        for g in gates
        if g.get("status") == "DONE"
    )

    in_progress_hours = sum(
        gate_weight(g)
        for g in gates
        if g.get("status") == "IN_PROGRESS"
    )

    verified_progress = (
        completed_hours / total_hours * 100
        if total_hours else 0
    )

    active = next(
        (
            g for g in gates
            if g.get("status") == "IN_PROGRESS"
        ),
        None
    )

    remaining_hours = max(
        total_hours - completed_hours,
        0
    )

    return {
        "total_estimated_hours": total_hours,
        "completed_estimated_hours": completed_hours,
        "active_estimated_hours": in_progress_hours,
        "remaining_estimated_hours": remaining_hours,
        "verified_progress_percent": round(
            verified_progress,
            1
        ),
        "active_gate": (
            active["id"]
            if active else None
        ),
        "active_gate_name": (
            active["name"]
            if active else None
        ),
    }


def bar(percent, width=30):
    filled = round(width * percent / 100)
    return "[" + "#" * filled + "." * (width - filled) + "]"


def main():
    plan = load_plan()
    git = git_state()
    calc = calculate(plan)

    print()
    print("=" * 64)
    print("             SLH LAUNCH CONTROL")
    print("=" * 64)

    print()
    print("SOURCE OF TRUTH:", plan["source_of_truth"])
    print("GENERATED:", datetime.now(timezone.utc).isoformat())

    print()
    print("GIT")
    print("  HEAD:        ", git["head"])
    print("  ORIGIN/MAIN: ", git["origin_main"])
    print("  SYNCED:      ", "PASS" if git["synced"] else "FAIL")
    print(
        "  WORKTREE:    ",
        "CLEAN" if git["worktree_clean"]
        else f"{len(git['uncommitted_files'])} uncommitted"
    )

    print()
    print("GATES")

    for gate in plan["gates"]:
        status = gate.get("status", "UNKNOWN")

        if status == "DONE":
            marker = "PASS"
        elif status == "IN_PROGRESS":
            marker = "RUN "
        elif status == "BLOCKED":
            marker = "BLOCK"
        else:
            marker = "TODO"

        print(
            f"  {gate['id']:>3} "
            f"{marker:<5} "
            f"{gate_weight(gate):>5.1f}h "
            f"{gate['name']}"
        )

    print()
    print("=" * 64)

    p = calc["verified_progress_percent"]

    print(
        f"VERIFIED PROGRESS: "
        f"{p:>5.1f}% "
        f"{bar(p)}"
    )

    print(
        f"COMPLETED WORK:    "
        f"{calc['completed_estimated_hours']:.1f}h"
    )

    print(
        f"REMAINING ESTIMATE: "
        f"{calc['remaining_estimated_hours']:.1f}h"
    )

    print(
        f"ACTIVE GATE:       "
        f"{calc['active_gate']} — "
        f"{calc['active_gate_name']}"
    )

    print("=" * 64)

    blockers = []

    if not git["synced"]:
        blockers.append("GIT_NOT_SYNCED")

    if not git["worktree_clean"]:
        blockers.append("WORKTREE_NOT_CLEAN")

    if blockers:
        print()
        print("BLOCKERS:")
        for blocker in blockers:
            print("  -", blocker)

    print()
    print("ALPHA STATUS")

    if all(
        gate.get("status") == "DONE"
        for gate in plan["gates"]
    ):
        print("  ALPHA READY")
    else:
        print("  NOT READY")
        print("  Rule: every launch gate must have evidence.")

    print()
    print("=" * 64)


if __name__ == "__main__":
    main()
