"""Canonical revenue read model for the SLH MCP control plane."""

from __future__ import annotations

from core import revenue_ledger


def revenue_status() -> dict:
    summary = revenue_ledger.summary()
    return {
        "events": int(summary.get("events", 0)),
        "totals": {str(k): float(v) for k, v in summary.get("totals", {}).items()},
        "source_of_truth": "state.db.json:revenue_ledger",
        "meaning": "confirmed external revenue events; not user Credits",
    }


def revenue_events(limit: int = 100) -> list[dict]:
    import state_manager
    limit = int(limit)
    if limit < 1 or limit > 500:
        raise ValueError("INVALID_LIMIT")
    db = state_manager.load_db()
    rows = db.get("revenue_ledger", [])
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows[-limit:]]


def _tool_revenue_status():
    return revenue_status()


def _tool_revenue_events(limit: int = 100):
    return revenue_events(limit)
