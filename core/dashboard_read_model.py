"""Unified dashboard snapshot for SLH OS Control Plane.

Read-only. Aggregates existing sources of truth into one view.
No mutation. No balance changes. No external writes.
"""

import json
from pathlib import Path

from core.investor_read_model import get_investor_snapshot
from core.alpha_control_plane import alpha_state
from store.engine import load_items


def _safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        return {"error": f"{type(e).__name__}"}


def _onchain(uid):
    try:
        from core import slh_api_client
        data = slh_api_client.get_balances(uid)
        if isinstance(data, dict):
            return data
    except Exception as e:
        return {"error": f"{type(e).__name__}"}
    return {}


def _system_health():
    health = {"alpha": "unknown", "store_items": 0, "stars_items": 0}
    try:
        db = json.loads(Path("state/db.json").read_text(encoding="utf-8-sig"))
        health["users"] = len(db.get("users", {}))
        health["agents"] = len(db.get("agents", {}))
        health["tasks"] = len(db.get("tasks", {}))
    except Exception as e:
        health["db_error"] = type(e).__name__
    try:
        items = load_items()
        health["store_items"] = len(items)
        health["stars_items"] = sum(
            1 for v in items.values()
            if isinstance(v, dict)
            and isinstance(v.get("price_stars"), int)
            and v["price_stars"] > 0
        )
    except Exception as e:
        health["store_error"] = type(e).__name__
    try:
        health["alpha"] = (alpha_state() or {}).get("status", "unknown")
    except Exception:
        health["alpha"] = "error"
    return health


def get_dashboard(uid):
    uid = str(uid)
    snapshot = get_investor_snapshot(uid)
    return {
        "identity": snapshot.get("identity", {}),
        "wallet": snapshot.get("wallet", {}),
        "onchain": _onchain(uid),
        "academy": snapshot.get("academy", {}),
        "tasks": snapshot.get("tasks", {}),
        "alpha": snapshot.get("alpha", {}),
        "rewards": snapshot.get("rewards", {}),
        "airdrop": snapshot.get("airdrop", {}),
        "system": _system_health(),
    }
