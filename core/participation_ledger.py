"""Dedicated, atomic ledger for the future SLH Participation product."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

import state_manager


LEDGER_FILE = "participation_ledger.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "positions": {},
        "revenue_pools": {},
        "reward_events": {},
        "settlements": {},
        "audit": [],
    }


def load() -> dict[str, Any]:
    data = state_manager.load_json(LEDGER_FILE, default=None)
    if not isinstance(data, dict):
        return _default()
    return data


def update(mutate: Callable[[dict[str, Any]], Any]) -> Any:
    def wrapped(data: dict[str, Any]):
        if not isinstance(data, dict):
            data = _default()
        data.setdefault("schema_version", 1)
        data.setdefault("positions", {})
        data.setdefault("revenue_pools", {})
        data.setdefault("reward_events", {})
        data.setdefault("settlements", {})
        data.setdefault("audit", [])
        return mutate(data)

    return state_manager.atomic_json_update(LEDGER_FILE, wrapped, default=_default())


def append_audit(data: dict[str, Any], *, event: str, event_id: str, payload: dict[str, Any] | None = None) -> None:
    data.setdefault("audit", []).append({
        "event": str(event),
        "event_id": str(event_id),
        "timestamp": _now(),
        "payload": dict(payload or {}),
    })
