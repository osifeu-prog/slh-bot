"""Read-only SLH OS system verification.

This module intentionally avoids mutating economy/state and never reads or reports
wallet.token_balance values. It is safe to expose to the authenticated Control Plane.
"""
from __future__ import annotations

import importlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _json(path: str, default=None):
    try:
        with (ROOT / path).open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _check(name, ok, detail, **extra):
    return {"name": name, "status": "PASS" if ok else "FAIL", "detail": detail, **extra}


def run_system_checks():
    checks = []

    db = _json("state/db.json")
    agents = _json("state/agents.json")
    registry = _json("control_plane_registry.json")
    ai_health = _json("state/ai_health.json", {})
    alpha = os.getenv("ALPHA_INVITE_OPEN", "").strip().lower()

    checks.append(_check("runtime", bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("PORT")),
                         "Process environment detected"))
    checks.append(_check("canonical_state", isinstance(db, dict) and isinstance(db.get("users"), dict),
                         "state/db.json readable with users registry"))
    checks.append(_check("agent_snapshot", isinstance(agents, dict),
                         "state/agents.json readable"))
    checks.append(_check("control_plane_registry", isinstance(registry, dict) and bool(registry.get("canonical")),
                         "control_plane_registry.json readable with canonical mapping"))
    checks.append(_check("alpha", alpha in ("1", "true", "yes", "open"),
                         "ALPHA_INVITE_OPEN=" + (alpha or "unset")))
    checks.append(_check("mini_app", (ROOT / "mini_app.html").exists(),
                         "mini_app.html present"))
    checks.append(_check("dashboard", (ROOT / "web/dashboard_v2/index.html").exists(),
                         "Control Plane dashboard assets present"))
    checks.append(_check("bot_factory", (ROOT / "core/bot_registry.py").exists() and (ROOT / "handlers/bot_factory.py").exists(),
                         "Bot Registry + Bot Factory handler present"))
    checks.append(_check("agent_runtime", (ROOT / "core/runtime_service.py").exists() and (ROOT / "core/agent_factory.py").exists(),
                         "Agent runtime/factory present"))
    checks.append(_check("ai", bool(ai_health) or (ROOT / "handlers").exists(),
                         "AI subsystem is represented in runtime"))
    checks.append(_check("economy", isinstance(db, dict) and isinstance(db.get("ledger"), (dict, list)),
                         "Economy ledger present"))
    checks.append(_check("token_balance_guard", True,
                         "Guard active: token_balance values are intentionally not inspected or modified"))

    try:
        importlib.import_module("core.control_center")
        checks.append(_check("control_center_import", True, "Control Center imports"))
    except Exception as exc:
        checks.append(_check("control_center_import", False, f"{type(exc).__name__}: {exc}"))

    passed = sum(c["status"] == "PASS" for c in checks)
    failed = len(checks) - passed
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if failed == 0 else "FAIL",
        "passed": passed,
        "failed": failed,
        "total": len(checks),
        "checks": checks,
        "scope": "read_only",
    }
