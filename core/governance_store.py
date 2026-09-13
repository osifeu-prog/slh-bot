"""Canonical Governance state access.

Governance is stored under state/db.json['governance'] and mutated through
state_manager.atomic_update.  A legacy state/governance.json is accepted only
as a one-time migration source when the canonical key is absent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from state_manager import atomic_update, load_db

ROOT = Path(__file__).resolve().parents[1]
LEGACY_GOV_PATH = ROOT / "state" / "governance.json"


def _read_legacy() -> dict[str, Any] | None:
    if not LEGACY_GOV_PATH.exists():
        return None
    try:
        value = json.loads(LEGACY_GOV_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _canonical_from_db(db: dict[str, Any]) -> dict[str, Any] | None:
    value = db.get("governance")
    return value if isinstance(value, dict) else None


def load_governance() -> dict[str, Any]:
    """Read canonical Governance state without mutating persistent state.

    If canonical state is absent, legacy governance.json is used as a
    compatibility read source until the migration is performed by
    ``ensure_canonical``.  No read operation writes state.
    """
    db = load_db()
    canonical = _canonical_from_db(db)
    if canonical is not None:
        return canonical

    legacy = _read_legacy()
    if legacy is not None:
        return legacy

    return {}


def save_governance(governance: dict[str, Any]) -> Any:
    """Persist Governance under the canonical db.json key atomically."""
    if not isinstance(governance, dict):
        raise TypeError("governance must be a dict")

    def mutate(db: dict[str, Any]) -> None:
        db["governance"] = governance

    return atomic_update(mutate)


def ensure_canonical() -> dict[str, Any]:
    """Migrate legacy Governance into db.json once, preserving all data.

    If db.json already has a governance object it is returned unchanged.
    The legacy file is never overwritten or deleted by this function.
    """
    def mutate(db: dict[str, Any]) -> dict[str, Any]:
        current = _canonical_from_db(db)
        if current is not None:
            return current

        legacy = _read_legacy()
        if legacy is None:
            db["governance"] = {}
            return db["governance"]

        migrated = dict(legacy)
        migrated["source_of_truth"] = "state/db.json"
        db["governance"] = migrated
        return migrated

    return atomic_update(mutate)


def update_governance(mutator: Callable[[dict[str, Any]], Any]) -> Any:
    """Atomically load, mutate and persist canonical Governance state."""
    def mutate(db: dict[str, Any]) -> Any:
        gov = _canonical_from_db(db)
        if gov is None:
            legacy = _read_legacy()
            gov = dict(legacy) if legacy is not None else {}
            gov["source_of_truth"] = "state/db.json"
            db["governance"] = gov
        return mutator(gov)

    return atomic_update(mutate)
