"""Canonical read-only system checks for SLH OS.

These checks inspect existing sources of truth only. They never write DB state,
change balances, open settlement gates, sign transactions, or broadcast.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


REQUIRED_DB_KEYS = ("users", "transactions", "ledger")
REQUIRED_UX_IDS = ("balance", "move", "growth", "investor", "profile", "bh", "bb", "bm", "bg", "binv")


def check_db() -> dict[str, Any]:
    try:
        import state_manager

        db = state_manager.load_db()
        missing = [key for key in REQUIRED_DB_KEYS if key not in db]
        if missing:
            return {"ok": False, "detail": "missing keys: " + ", ".join(missing)}
        users = db.get("users")
        return {
            "ok": isinstance(users, dict),
            "detail": f"state/db.json readable · users={len(users) if isinstance(users, dict) else 0}",
        }
    except Exception as exc:
        return {"ok": False, "detail": f"state/db.json unreadable: {type(exc).__name__}"}


def check_commands() -> dict[str, Any]:
    try:
        from core.runtime_command_evidence import snapshot_runtime

        snapshot = snapshot_runtime("Me_ad_main")
        collisions = int(snapshot.get("collision_count") or 0)
        required = {"help", "check", "check_ux", "check_money", "check_bnb", "check_ton"}
        registered = set(snapshot.get("commands", {}))
        missing = sorted("/" + cmd for cmd in required if "/" + cmd not in registered)
        ok = collisions == 0 and not missing
        detail = (
            f"handlers={snapshot.get('total_message_handlers')} "
            f"commands={snapshot.get('unique_commands')} collisions={collisions}"
        )
        if missing:
            detail += " · missing=" + ", ".join(missing)
        return {
            "ok": ok,
            "detail": detail,
            "collisions": collisions,
            "missing": missing,
        }
    except KeyError:
        return {"ok": False, "detail": "runtime bot Me_ad_main is not registered"}
    except Exception as exc:
        return {"ok": False, "detail": f"runtime command snapshot failed: {type(exc).__name__}"}


def check_ux() -> dict[str, Any]:
    try:
        html = Path("mini_app.html").read_text(encoding="utf-8")
        checks = []
        for item in REQUIRED_UX_IDS:
            marker = f'id="{item}"'
            checks.append({"name": marker, "ok": marker in html})
        required_text = (
            "Home",
            "Balance",
            "Move",
            "Grow",
            "Investor",
            "SLH · פנימי",
            "SLH · on-chain",
        )
        for item in required_text:
            checks.append({"name": item, "ok": item in html})
        ok = all(item["ok"] for item in checks)
        return {
            "ok": ok,
            "detail": "Mini App public shell contract present" if ok else "Mini App shell contract incomplete",
            "checks": checks,
        }
    except Exception as exc:
        return {"ok": False, "detail": f"Mini App source check failed: {type(exc).__name__}", "checks": []}


def check_money(uid: str) -> dict[str, Any]:
    checks = []
    try:
        from core import economy_service

        balance = economy_service.get_balance_safe(uid)
        staked = economy_service.get_staked_safe(uid)
        checks.append({"name": f"Credits readable ({balance})", "ok": True, "detail": ""})
        checks.append({"name": f"Staked readable ({staked})", "ok": True, "detail": ""})
    except Exception as exc:
        checks.append({"name": "Economy read", "ok": False, "detail": type(exc).__name__})

    try:
        from handlers.exchange_handler import _assert_invariants
        import state_manager

        _assert_invariants(state_manager.load_db())
        checks.append({"name": "Exchange reserve invariants", "ok": True, "detail": ""})
    except Exception as exc:
        checks.append({"name": "Exchange reserve invariants", "ok": False, "detail": type(exc).__name__})

    try:
        from core.revenue_ledger import summary

        data = summary()
        checks.append(
            {"name": f"Revenue ledger readable ({int(data.get('events', 0))} events)", "ok": True, "detail": ""}
        )
    except Exception as exc:
        checks.append({"name": "Revenue ledger", "ok": False, "detail": type(exc).__name__})

    ok = all(item["ok"] for item in checks)
    return {
        "ok": ok,
        "detail": "internal financial reads/invariants PASS" if ok else "one or more financial read checks failed",
        "checks": checks,
    }


def check_bnb() -> dict[str, Any]:
    try:
        from core.bnb_gate import bnb_opening_evidence, bnb_readiness

        gate = bnb_readiness()
        evidence = bnb_opening_evidence()
        empirical = evidence.get("empirical_settlement") or {}
        empirical_status = str(empirical.get("status") or "PENDING_EMPIRICAL")
        ready = bool(gate.get("ready")) and not bool(evidence.get("blockers"))
        public_open = bool(gate.get("effective_open"))
        ok = ready and not public_open and empirical_status == "PASS"
        detail = (
            "BNB gate CLOSED; readiness valid; empirical proof complete"
            if ok
            else "BNB gate CLOSED safely; empirical proof still pending"
            if ready and not public_open
            else "BNB readiness requires attention"
        )
        return {
            "ok": ok,
            "detail": detail,
            "public_open": public_open,
            "ready": ready,
            "empirical_status": empirical_status,
            "confirmations_required": gate.get("confirmations_required"),
            "blockers": evidence.get("blockers", []),
        }
    except Exception as exc:
        return {
            "ok": False,
            "detail": f"BNB read-only check failed: {type(exc).__name__}",
            "public_open": False,
            "ready": False,
            "empirical_status": "UNKNOWN",
            "confirmations_required": 0,
        }


def check_ton(uid: str) -> dict[str, Any]:
    try:
        from core.ton_deposit_service import ton_readiness
        import state_manager

        readiness = ton_readiness()
        db = state_manager.load_db()
        replay = db.get("ton_replay_evidence", {}) if isinstance(db, dict) else {}
        user_replay = replay.get(str(uid)) if isinstance(replay, dict) else None
        replay_label = "present" if isinstance(user_replay, dict) else "not recorded for this UID"
        ok = bool(readiness.get("ready")) and bool(readiness.get("effective_open"))
        detail = "TON public gate OPEN and readiness valid" if ok else "TON readiness/gate requires attention"
        return {
            "ok": ok,
            "detail": detail,
            "public_open": bool(readiness.get("effective_open")),
            "ready": bool(readiness.get("ready")),
            "rate": readiness.get("rate") or "0",
            "replay_evidence": replay_label,
        }
    except Exception as exc:
        return {
            "ok": False,
            "detail": f"TON read-only check failed: {type(exc).__name__}",
            "public_open": False,
            "ready": False,
            "rate": "0",
            "replay_evidence": "unknown",
        }
