"""Canonical Governance state access.

Governance is stored under state/db.json['governance'] and mutated through
state_manager.atomic_update.  A legacy state/governance.json is accepted only
as a one-time migration source when the canonical key is absent.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from state_manager import atomic_update, load_db
from core import profile_manager

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


def record_vote(
    *,
    proposal_id: int,
    voter_uid: str,
    choice: str,
    reward_points: int = 0,
    now: str | None = None,
) -> dict[str, Any]:
    """Record one canonical Governance vote atomically."""
    try:
        proposal_id = int(proposal_id)
    except (TypeError, ValueError):
        raise ValueError("PROPOSAL_ID_INVALID")

    choice = str(choice).strip().lower()
    if choice not in ("yes", "no", "abstain"):
        raise ValueError("VOTE_CHOICE_INVALID")

    voter_uid = str(voter_uid).strip()
    if not voter_uid:
        raise ValueError("VOTER_REQUIRED")

    reward_points = max(int(reward_points or 0), 0)
    timestamp = now or datetime.now(timezone.utc).isoformat()

    def mutate(db: dict[str, Any]) -> dict[str, Any]:
        gov = _canonical_from_db(db)
        if gov is None:
            gov = {"source_of_truth": "state/db.json"}
            db["governance"] = gov

        proposals = gov.setdefault("proposals", [])
        proposal = None
        for item in proposals:
            try:
                item_id = int(item.get("id", 0))
            except (TypeError, ValueError):
                continue
            if item_id == proposal_id:
                proposal = item
                break

        if proposal is None:
            raise ValueError("PROPOSAL_NOT_FOUND")
        if proposal.get("status") != "open":
            raise ValueError("PROPOSAL_CLOSED")

        individual_votes = gov.setdefault("individual_votes", {})
        vote_key = f"p{proposal_id}_{voter_uid}"
        if vote_key in individual_votes:
            existing = individual_votes[vote_key]
            return {
                "status": "already_voted",
                "proposal_id": proposal_id,
                "voter": voter_uid,
                "choice": existing.get("choice"),
                "weight": existing.get("weight", 1),
                "points_awarded": 0,
                "slh_context": existing.get("slh_context", {}),
            }

        users = db.setdefault("users", {})
        user = users.setdefault(voter_uid, profile_manager._default_user(voter_uid))
        role = str(user.get("role", "student")).lower()
        weights = gov.get("rules", {}).get("vote_weights", {})
        weight = int(weights.get(role, 1) or 1)

        wallet = user.get("wallet", {}) or {}
        game = user.get("gamification", {}) or {}
        slh_context = {
            "token_balance": wallet.get("token_balance", 0) or 0,
            "live_token_balance": wallet.get("live_token_balance", 0) or 0,
            "points_before": game.get("points", 0) or 0,
            "recorded_at": timestamp,
        }

        individual_votes[vote_key] = {
            "proposal_id": proposal_id,
            "voter": voter_uid,
            "choice": choice,
            "weight": weight,
            "timestamp": timestamp,
            "points_awarded": reward_points,
            "slh_context": slh_context,
        }

        votes = proposal.setdefault("votes", {})
        if choice == "yes":
            votes["yes"] = votes.get("yes", 0) + 1
            votes["weighted_yes"] = votes.get("weighted_yes", 0) + weight
        elif choice == "no":
            votes["no"] = votes.get("no", 0) + 1
            votes["weighted_no"] = votes.get("weighted_no", 0) + weight
        else:
            votes["abstain"] = votes.get("abstain", 0) + 1

        points_after = game.get("points", 0) or 0
        if reward_points > 0:
            points_after = profile_manager.add_points_in_db(
                db,
                voter_uid,
                reward_points,
                reason="governance_vote",
                meta={
                    "idempotency_key": f"governance_vote:{proposal_id}:{voter_uid}",
                    "proposal_id": proposal_id,
                    "choice": choice,
                },
            ).get("points", 0)

        return {
            "status": "recorded",
            "proposal_id": proposal_id,
            "voter": voter_uid,
            "choice": choice,
            "weight": weight,
            "points_awarded": reward_points,
            "points_after": points_after,
            "slh_context": slh_context,
        }

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
