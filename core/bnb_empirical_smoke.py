"""Owner-only live BNB settlement smoke.

This module exists to close the empirical release gate with one real,
controlled transaction. It never holds or receives private keys and never
opens the public BNB settlement flag.
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
    pass


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
        raise BNBEmpiricalSmokeError(str(verified.get("error") or "BNB_TX_NOT_VERIFIED"))

    sender = str(verified.get("from") or "")
    if sender.lower() != str(binding.get("address") or "").lower():
        raise BNBEmpiricalSmokeError("BNB_TX_SENDER_NOT_BOUND_WALLET")

    before = get_balance_safe(uid)
    first = settle_bnb_deposit(uid, tx_hash, empirical_smoke=True)
    after_first = get_balance_safe(uid)

    second = settle_bnb_deposit(uid, tx_hash, empirical_smoke=True)
    after_second = get_balance_safe(uid)

    key = f"bnb:deposit:{tx_hash.lower()}"
    db = state_manager.load_db()
    ledger = db.get("ledger", [])
    matching = [
        entry for entry in ledger
        if entry.get("meta", {}).get("idempotency_key") == key
    ]

    credits = float(first.get("credits", 0))
    arithmetic_ok = abs(float(before) + credits - float(after_first)) <= 1e-12
    replay_ok = float(after_second) == float(after_first)
    single_entry_ok = len(matching) == 1
    first_not_replay = first.get("idempotent") is False
    second_replay = second.get("idempotent") is True

    status = (
        arithmetic_ok
        and replay_ok
        and single_entry_ok
        and first_not_replay
        and second_replay
    )

    if not status:
        raise BNBEmpiricalSmokeError(
            "BNB_EMPIRICAL_SMOKE_RECONCILIATION_FAILED"
        )

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
        "balance_before": float(before),
        "balance_after": float(after_first),
        "replay_balance_after": float(after_second),
        "ledger_entries_for_idempotency_key": len(matching),
        "confirmations": verified.get("confirmations"),
        "from_bound_wallet": True,
        "gate_remained_closed": True,
    }

    def persist(db):
        db.setdefault("settlement_evidence", {})["bnb"] = evidence
        return evidence

    state_manager.atomic_update(persist)
    return evidence
