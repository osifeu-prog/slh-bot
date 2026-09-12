"""Deterministic, read-only Alpha readiness evaluator.

This module deliberately does not mutate production state and does not rely on an
LLM-generated readiness claim. It evaluates the small set of launch-critical
contracts from the canonical DB/codebase and returns BLOCKED or READY.
"""

from pathlib import Path
import importlib.util
import json
import os
import time

ROOT = Path(__file__).resolve().parent.parent


def _check(name, passed, detail=""):
    return {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}


def evaluate():
    checks = []

    gateway = ROOT / "bot_gateway.py"
    checks.append(_check("runtime", gateway.exists(), "bot_gateway.py present"))
    checks.append(_check("run_bot_enabled", str(os.getenv("RUN_BOT", "")).strip() == "1",
                         "RUN_BOT=1 required in the active runtime"))

    db_path = ROOT / "state" / "db.json"
    try:
        db = json.loads(db_path.read_text(encoding="utf-8"))
        checks.append(_check("canonical_state", isinstance(db, dict) and "users" in db,
                             "state/db.json readable with users"))
    except Exception as exc:
        db = {}
        checks.append(_check("canonical_state", False, type(exc).__name__))

    users = db.get("users", {}) if isinstance(db, dict) else {}
    checks.append(_check("economy", isinstance(users, dict), "users wallet store available"))

    ledger = db.get("slh_token_ledger") if isinstance(db, dict) else None
    checks.append(_check("slh_integrity", isinstance(ledger, list),
                         "SLH token ledger available"))

    distribution = ROOT / "core" / "slh_distribution.py"
    checks.append(_check("slh_transfer", distribution.exists(),
                         "SLH distribution authority present"))

    payment = ROOT / "handlers" / "payment_handler.py"
    checks.append(_check("payments", payment.exists(), "payment handler present"))

    exchange = ROOT / "handlers" / "exchange_handler.py"
    if not exchange.exists():
        exchange = ROOT / "core" / "exchange_service.py"
    checks.append(_check("exchange", exchange.exists(), "exchange path present"))

    staking = ROOT / "core" / "staking_service.py"
    checks.append(_check("staking", staking.exists(), "staking service present"))

    reward_v2 = ROOT / "core" / "reward_engine_v2.py"
    checks.append(_check("staking_reward_settlement", reward_v2.exists(),
                         "reward settlement implementation present"))

    onboarding = ROOT / "handlers" / "onboarding_v2.py"
    checks.append(_check("onboarding", onboarding.exists(), "onboarding handler present"))

    blockers = [c for c in checks if c["status"] != "PASS"]
    return {
        "status": "BLOCKED" if blockers else "READY",
        "blockers": blockers,
        "checks": checks,
        "timestamp": time.time(),
    }


def format_report(result):
    lines = ["ALPHA CONTROL PLANE", "────────────────────"]
    for check in result["checks"]:
        lines.append(f"{check['name']:<28} {check['status']}")
    lines += ["────────────────────",
              f"BLOCKERS: {len(result['blockers'])}",
              f"STATUS: {result['status']}"]
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_report(evaluate()))
