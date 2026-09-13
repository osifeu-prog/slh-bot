"""Deterministic Alpha readiness and open-state control plane.

Readiness is evaluated from concrete runtime/code/state contracts. No LLM-generated
readiness claim is accepted. ``evaluate`` is read-only; ``open_alpha`` is the only
state-changing operation and is owner-gated by its caller.
"""

from pathlib import Path
import json
import os
import time
from datetime import datetime, timezone

import state_manager
from core.exec_policy import is_owner

ROOT = Path(__file__).resolve().parent.parent
ALPHA_KEY = "alpha_control"


def _check(name, passed, detail=""):
    return {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}


def evaluate():
    checks = []
    gateway = ROOT / "bot_gateway.py"
    checks.append(_check("runtime", gateway.exists(), "bot_gateway.py present"))

    # RUN_BOT is an optional deployment hint. If explicitly configured it must be 1;
    # absence must not falsely block an already-running gateway/runtime.
    run_bot = str(os.getenv("RUN_BOT", "")).strip()
    checks.append(_check("run_bot_config", run_bot in ("", "1"),
                         "RUN_BOT unset or RUN_BOT=1"))

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
    checks.append(_check("slh_integrity", isinstance(ledger, list), "SLH token ledger available"))
    checks.append(_check("slh_transfer", (ROOT / "core" / "slh_distribution.py").exists(),
                         "SLH distribution authority present"))
    checks.append(_check("payments", (ROOT / "handlers" / "payment_handler.py").exists(),
                         "payment handler present"))

    exchange = ROOT / "handlers" / "exchange_handler.py"
    if not exchange.exists():
        exchange = ROOT / "core" / "exchange_service.py"
    checks.append(_check("exchange", exchange.exists(), "exchange path present"))
    checks.append(_check("staking", (ROOT / "core" / "staking_service.py").exists(),
                         "staking service present"))

    settlement = ROOT / "core" / "staking_reward_settlement.py"
    try:
        from core.staking_reward_settlement import settle_position_reward
        settlement_ok = settlement.exists() and callable(settle_position_reward)
    except Exception:
        settlement_ok = False
    checks.append(_check("staking_reward_settlement", settlement_ok,
                         "staking reward settlement authority present"))

    checks.append(_check("onboarding", (ROOT / "handlers" / "onboarding_v2.py").exists(),
                         "onboarding handler present"))

    blockers = [c for c in checks if c["status"] != "PASS"]
    return {"status": "BLOCKED" if blockers else "READY", "blockers": blockers,
            "checks": checks, "timestamp": time.time()}


def format_report(result):
    lines = ["ALPHA CONTROL PLANE", "────────────────────"]
    for check in result["checks"]:
        lines.append(f"{check['name']:<28} {check['status']}")
    lines += ["────────────────────", f"BLOCKERS: {len(result['blockers'])}",
              f"STATUS: {result['status']}"]
    return "\n".join(lines)


def alpha_state():
    db = state_manager.load_db()
    value = db.get(ALPHA_KEY, {}) if isinstance(db, dict) else {}
    return dict(value) if isinstance(value, dict) else {}


def open_alpha(owner_id):
    """Open Alpha only when the deterministic gate is READY and caller is owner."""
    if not is_owner(owner_id):
        raise PermissionError("Owner only.")

    result = evaluate()
    if result["status"] != "READY":
        raise RuntimeError(format_report(result))
    owner_id = str(owner_id)

    def mutate(db):
        state = db.setdefault(ALPHA_KEY, {})
        if state.get("status") == "OPEN":
            return dict(state)
        now = datetime.now(timezone.utc).isoformat()
        state.update({"status": "OPEN", "opened_by": owner_id,
                      "opened_at": now, "gate_timestamp": result["timestamp"]})
        return dict(state)

    return state_manager.atomic_update(mutate)


if __name__ == "__main__":
    print(format_report(evaluate()))
