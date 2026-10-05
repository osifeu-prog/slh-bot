"""Owner-only empirical BNB settlement smoke and evidence persistence.

This module never sends or signs a transaction and never opens the public
BNB settlement gate. It consumes one already-confirmed, real transaction
and exercises the canonical settlement path twice to prove reconciliation
and idempotency.
"""
from __future__ import annotations

from datetime import datetime, timezone

import state_manager

from core.authority import is_owner
from core.bnb_deposit_service import settle_bnb_deposit
from core.bnb_gate import bnb_deposits_open
from core.deposit_monitor import verify_bnb_deposit
from core.economy_service import get_balance_safe
from core.wallet_binding import get_binding


class BNBEmpiricalSmokeError(ValueError):
    """Raised when the controlled empirical smoke cannot be proven."""


def _existing_evidence() -> dict | None:
    db = state_manager.load_db()
    evidence = db.get("settlement_evidence", {})
    bnb = evidence.get("bnb") if isinstance(evidence, dict) else None
    return bnb if isinstance(bnb, dict) else None


def run(uid: str, tx_hash: str) -> dict:
    uid = str(uid)
    tx_hash = str(tx_hash or "").strip()

    if not is_owner(uid):
        raise BNBEmpiricalSmokeError("BNB_EMPIRICAL_SMOKE_OWNER_ONLY")
    if bnb_deposits_open():
        raise BNBEmpiricalSmokeError("BNB_EMPIRICAL_SMOKE_REQUIRES_CLOSED_GATE")
    if not tx_hash:
        raise BNBEmpiricalSmokeError("INVALID_TX_HASH")

    existing = _existing_evidence()
    if existing and existing.get("status") == "PASS":
        raise BNBEmpiricalSmokeError("BNB_EMPIRICAL_SMOKE_ALREADY_COMPLETED")

    binding = get_binding(uid)
    if not binding:
        raise BNBEmpiricalSmokeError("BNB_WALLET_NOT_VERIFIED")

    verified = verify_bnb_deposit(tx_hash)
    if not verified.get("ok"):
        raise BNBEmpiricalSmokeError(
            str(verified.get("error") or "BNB_TX_NOT_VERIFIED")
        )

    sender = str(verified.get("from") or "")
    bound = str(binding.get("address") or "")
    if not sender or sender.lower() != bound.lower():
        raise BNBEmpiricalSmokeError("BNB_TX_SENDER_NOT_BOUND_WALLET")

    before = float(get_balance_safe(uid))
    first = settle_bnb_deposit(uid, tx_hash)
    after_first = float(get_balance_safe(uid))

    second = settle_bnb_deposit(uid, tx_hash)
    after_second = float(get_balance_safe(uid))

    key = f"bnb:deposit:{tx_hash.lower()}"
    db = state_manager.load_db()
    ledger = db.get("ledger", [])
    matching = [
        entry
        for entry in ledger
        if entry.get("meta", {}).get("idempotency_key") == key
    ]

    credits = float(first.get("credits", 0))
    arithmetic_ok = abs(before + credits - after_first) <= 1e-12
    replay_ok = after_second == after_first
    single_entry_ok = len(matching) == 1
    first_not_replay = first.get("idempotent") is False
    second_replay = second.get("idempotent") is True
    gate_stayed_closed = not bnb_deposits_open()

    status = all(
        (
            arithmetic_ok,
            replay_ok,
            single_entry_ok,
            first_not_replay,
            second_replay,
            gate_stayed_closed,
        )
    )
    if not status:
        raise BNBEmpiricalSmokeError("BNB_EMPIRICAL_SMOKE_RECONCILIATION_FAILED")

    evidence = {
        "status": "PASS",
        "uid": uid,
        "tx_hash": tx_hash,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "wallet_binding": True,
            "tx_verification": True,
            "idempotency": True,
            "atomic_ledger": True,
            "reconciliation": True,
        },
        "amount_wei": int(first["amount_wei"]),
        "credits": credits,
        "balance_before": before,
        "balance_after": after_first,
        "replay_balance_after": after_second,
        "ledger_entries_for_idempotency_key": len(matching),
        "confirmations": verified.get("confirmations"),
        "from_bound_wallet": True,
        "to_treasury": str(verified.get("to") or ""),
        "gate_remained_closed": gate_stayed_closed,
    }

    def persist(db):
        db.setdefault("settlement_evidence", {})["bnb"] = evidence
        return evidence

    state_manager.atomic_update(persist)
    return evidence
