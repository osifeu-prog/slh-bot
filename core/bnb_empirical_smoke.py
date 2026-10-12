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


def _existing_evidence(db=None) -> dict | None:
    if db is None:
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

    current_db = state_manager.load_db()
    existing = _existing_evidence(current_db)
    stale_existing = None
    if existing and existing.get("status") == "PASS":
        from core.bnb_gate import _effective_config, _empirical_evidence_revalidated

        current = _empirical_evidence_revalidated(
            existing, _effective_config(current_db), db=current_db
        )
        if current:
            raise BNBEmpiricalSmokeError("BNB_EMPIRICAL_SMOKE_ALREADY_COMPLETED")
        # Stored PASS is not authority when current chain or ledger evidence
        # contradicts it. Preserve the historical record in audit when a
        # different, valid TX later replaces it.
        stale_existing = dict(existing)

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
        root = db.setdefault("settlement_evidence", {})
        if not isinstance(root, dict):
            root = {}
            db["settlement_evidence"] = root
        previous = root.get("bnb")
        if (
            stale_existing
            and isinstance(previous, dict)
            and str(previous.get("tx_hash") or "").lower()
                == str(stale_existing.get("tx_hash") or "").lower()
            and previous.get("status") == "PASS"
        ):
            audit = db.setdefault("settlement_evidence_audit", [])
            if not isinstance(audit, list):
                audit = []
                db["settlement_evidence_audit"] = audit
            already_audited = any(
                isinstance(item, dict)
                and str(item.get("previous_tx_hash") or "").lower()
                    == str(previous.get("tx_hash") or "").lower()
                and item.get("disposition") == "INVALIDATED_BY_REVALIDATION"
                for item in audit
            )
            if not already_audited:
                audit.append({
                    "asset": "BNB",
                    "event": "STALE_SETTLEMENT_EVIDENCE_INVALIDATED",
                    "previous_tx_hash": str(previous.get("tx_hash") or ""),
                    "previous_status": str(previous.get("status") or ""),
                    "disposition": "INVALIDATED_BY_REVALIDATION",
                    "detected_at": evidence["observed_at"],
                    "reason": "Persisted PASS failed current chain/ledger revalidation.",
                    "previous_evidence": dict(previous),
                    "runtime_balance_unchanged_by_audit": True,
                })
                del audit[:-100]
        root["bnb"] = evidence
        return evidence

    state_manager.atomic_update(persist)
    return evidence


def reconcile_existing_settlement(uid: str, tx_hash: str) -> dict:
    """Prove a previously credited BNB TX by live idempotent replay, without re-crediting.

    The historical canonical ledger entry supplies the original balance delta.
    A fresh BSC RPC verification plus one idempotent settlement replay proves the
    same TX still resolves to that entry and does not change the current balance.
    This path never accepts a new TX or opens the public BNB gate.
    """
    uid = str(uid or "").strip()
    tx_hash = str(tx_hash or "").strip()
    if not is_owner(uid):
        return {"status": "FORBIDDEN"}
    if not re.fullmatch(r"0x[0-9a-fA-F]{64}", tx_hash):
        return {"status": "INVALID_TX_HASH"}

    from core.bnb_gate import (
        _effective_config,
        _empirical_evidence_revalidated,
        bnb_readiness,
        bnb_settlement_allowed,
    )

    if bnb_deposits_open():
        return {"status": "GATE_OPEN"}

    try:
        db = state_manager.load_db()
    except Exception:
        return {"status": "STATE_UNREADABLE"}
    if not isinstance(db, dict):
        return {"status": "STATE_UNREADABLE"}

    readiness = bnb_readiness(db)
    if not isinstance(readiness, dict) or readiness.get("ready") is not True:
        return {"status": "BNB_CONFIGURATION_NOT_READY"}
    if not bnb_settlement_allowed(uid, db):
        return {"status": "BNB_SETTLEMENT_NOT_AUTHORIZED"}

    existing_root = db.get("settlement_evidence", {})
    existing = existing_root.get("bnb") if isinstance(existing_root, dict) else None
    gate_config = _effective_config(db)
    if isinstance(existing, dict) and existing.get("status") == "PASS":
        if _empirical_evidence_revalidated(existing, gate_config, db=db):
            return {
                "status": "ALREADY_PASS",
                "tx_hash": existing.get("tx_hash"),
                "gate_remained_closed": not bnb_deposits_open(),
            }

    binding = get_binding(uid)
    if not isinstance(binding, dict) or not str(binding.get("address") or "").strip():
        return {"status": "BNB_WALLET_NOT_VERIFIED"}

    verified = verify_bnb_deposit(tx_hash)
    if not isinstance(verified, dict) or verified.get("ok") is not True:
        return {
            "status": "TX_NOT_VERIFIED",
            "detail": str((verified or {}).get("error") or "BNB_TX_NOT_VERIFIED")[:100],
        }
    verified_hash = str(verified.get("tx_hash") or "").strip()
    if not verified_hash or verified_hash.lower() != tx_hash.lower():
        return {"status": "TX_HASH_MISMATCH"}

    sender = str(verified.get("from") or "").strip()
    bound = str(binding.get("address") or "").strip()
    if not sender or sender.lower() != bound.lower():
        return {"status": "BNB_TX_SENDER_NOT_BOUND_WALLET"}

    treasury = str(gate_config.get("treasury_wallet") or "").strip()
    receiver = str(verified.get("to") or "").strip()
    if not treasury or not receiver or receiver.lower() != treasury.lower():
        return {"status": "BNB_TX_RECEIVER_NOT_CANONICAL_TREASURY"}

    try:
        amount_wei = int(verified.get("amount_wei") or 0)
        confirmations = int(verified.get("confirmations") or 0)
        required_confirmations = int(
            readiness.get("confirmations_required") or 15
        )
    except (TypeError, ValueError, OverflowError):
        return {"status": "TX_FIELDS_INVALID"}
    if amount_wei != 10**16:
        return {"status": "BNB_EMPIRICAL_AMOUNT_MISMATCH"}
    if required_confirmations < 1 or confirmations < required_confirmations:
        return {
            "status": "INSUFFICIENT_CONFIRMATIONS",
            "confirmations": confirmations,
            "required_confirmations": required_confirmations,
        }

    idempotency_key = f"bnb:deposit:{tx_hash.lower()}"
    ledger = db.get("ledger", [])
    if not isinstance(ledger, list):
        return {"status": "LEDGER_UNREADABLE"}
    matching = [
        entry for entry in ledger
        if isinstance(entry, dict)
        and isinstance(entry.get("meta"), dict)
        and str(entry["meta"].get("idempotency_key") or "").lower() == idempotency_key
    ]
    if len(matching) != 1:
        return {
            "status": "LEDGER_ENTRY_COUNT_MISMATCH",
            "ledger_entries": len(matching),
        }

    entry = matching[0]
    meta = entry.get("meta") or {}
    if str(entry.get("uid") or "") != uid or entry.get("reason") != "bnb:deposit":
        return {"status": "LEDGER_OWNER_OR_REASON_MISMATCH"}
    if str(meta.get("tx_hash") or "").lower() != tx_hash.lower():
        return {"status": "LEDGER_TX_HASH_MISMATCH"}
    if str(meta.get("from") or "").lower() != sender.lower():
        return {"status": "LEDGER_SENDER_MISMATCH"}
    if str(meta.get("to") or "").lower() != receiver.lower():
        return {"status": "LEDGER_TREASURY_MISMATCH"}
    try:
        if int(meta.get("bnb_amount_wei") or 0) != amount_wei:
            return {"status": "LEDGER_AMOUNT_WEI_MISMATCH"}
        credits = float(entry.get("amount"))
        before = float(entry.get("before"))
        after = float(entry.get("after"))
    except (TypeError, ValueError, OverflowError):
        return {"status": "LEDGER_FIELDS_INVALID"}
    expected_credits = float(Decimal(amount_wei) * Decimal(CREDITS_PER_BNB) / Decimal(10**18))
    if not all(math.isfinite(value) for value in (credits, before, after)):
        return {"status": "LEDGER_FIELDS_INVALID"}
    if abs(credits - expected_credits) > max(1e-9, abs(expected_credits) * 1e-9):
        return {"status": "LEDGER_CREDITS_MISMATCH"}
    if abs((before + credits) - after) > 1e-9:
        return {"status": "LEDGER_BALANCE_DELTA_MISMATCH"}

    try:
        current_before = float(get_balance_safe(uid))
        replay = settle_bnb_deposit(uid, tx_hash)
        current_after = float(get_balance_safe(uid))
    except Exception as exc:
        return {
            "status": "REPLAY_FAILED",
            "detail": str(exc)[:100] if str(exc) else type(exc).__name__,
        }

    if not isinstance(replay, dict):
        return {"status": "REPLAY_RESULT_INVALID"}
    if (
        replay.get("idempotent") is not True
        or str(replay.get("settlement_status") or "").upper() != "DUPLICATE"
        or abs(float(replay.get("credits", 0) or 0)) > 1e-12
    ):
        return {"status": "REPLAY_NOT_IDEMPOTENT"}
    if not all(math.isfinite(value) for value in (current_before, current_after)):
        return {"status": "REPLAY_BALANCE_INVALID"}
    if abs(current_before - current_after) > 1e-9:
        return {
            "status": "REPLAY_BALANCE_CHANGED",
            "balance_before": current_before,
            "balance_after": current_after,
        }
    if bnb_deposits_open():
        return {"status": "GATE_OPENED_UNEXPECTEDLY"}

    # Re-read after replay and ensure no duplicate entry or ledger drift occurred.
    try:
        db_after = state_manager.load_db()
    except Exception:
        return {"status": "STATE_UNREADABLE_AFTER_REPLAY"}
    ledger_after = db_after.get("ledger", []) if isinstance(db_after, dict) else []
    matching_after = [
        item for item in ledger_after
        if isinstance(item, dict)
        and isinstance(item.get("meta"), dict)
        and str(item["meta"].get("idempotency_key") or "").lower() == idempotency_key
    ] if isinstance(ledger_after, list) else []
    if len(matching_after) != 1:
        return {"status": "LEDGER_CHANGED_DURING_REPLAY"}
    entry_after = matching_after[0]
    if (
        str(entry_after.get("uid") or "") != uid
        or entry_after.get("reason") != "bnb:deposit"
        or abs(float(entry_after.get("amount", 0) or 0) - credits) > 1e-9
        or abs(float(entry_after.get("before", 0) or 0) - before) > 1e-9
        or abs(float(entry_after.get("after", 0) or 0) - after) > 1e-9
    ):
        return {"status": "LEDGER_CHANGED_DURING_REPLAY"}

    evidence = {
        "status": "PASS",
        "proof_mode": "existing_ledger_plus_live_replay",
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
        "amount_wei": amount_wei,
        "credits": credits,
        "balance_before": before,
        "balance_after": after,
        "replay_balance_after": after,
        "ledger_entries_for_idempotency_key": 1,
        "confirmations": confirmations,
        "from_bound_wallet": True,
        "to_treasury": receiver,
        "gate_remained_closed": True,
        "settlement_result_idempotent": True,
        "settlement_result_status": "DUPLICATE",
        "current_replay_balance_before": current_before,
        "current_replay_balance_after": current_after,
        "replay_observed_unchanged": True,
    }

    def persist(db_current):
        final_ledger = db_current.get("ledger", [])
        final_matches = [
            item for item in final_ledger
            if isinstance(item, dict)
            and isinstance(item.get("meta"), dict)
            and str(item["meta"].get("idempotency_key") or "").lower() == idempotency_key
        ] if isinstance(final_ledger, list) else []
        if len(final_matches) != 1:
            return {"status": "LEDGER_CHANGED_BEFORE_EVIDENCE_PERSIST"}
        current_entry = final_matches[0]
        if (
            str(current_entry.get("uid") or "") != uid
            or current_entry.get("reason") != "bnb:deposit"
            or abs(float(current_entry.get("amount", 0) or 0) - credits) > 1e-9
            or abs(float(current_entry.get("before", 0) or 0) - before) > 1e-9
            or abs(float(current_entry.get("after", 0) or 0) - after) > 1e-9
        ):
            return {"status": "LEDGER_CHANGED_BEFORE_EVIDENCE_PERSIST"}
        root = db_current.setdefault("settlement_evidence", {})
        if not isinstance(root, dict):
            root = {}
            db_current["settlement_evidence"] = root
        previous = root.get("bnb")
        if isinstance(previous, dict) and previous.get("status") == "PASS":
            audit = db_current.setdefault("settlement_evidence_audit", [])
            if not isinstance(audit, list):
                audit = []
                db_current["settlement_evidence_audit"] = audit
            already_audited = any(
                isinstance(item, dict)
                and str(item.get("previous_tx_hash") or "").lower()
                    == str(previous.get("tx_hash") or "").lower()
                and item.get("disposition") == "INVALIDATED_BY_REVALIDATION"
                for item in audit
            )
            if not already_audited:
                audit.append({
                    "asset": "BNB",
                    "event": "STALE_SETTLEMENT_EVIDENCE_INVALIDATED",
                    "previous_tx_hash": str(previous.get("tx_hash") or ""),
                    "previous_status": str(previous.get("status") or ""),
                    "disposition": "INVALIDATED_BY_REVALIDATION",
                    "detected_at": evidence["observed_at"],
                    "reason": "Existing settlement replay generated a fresh canonical proof.",
                    "previous_evidence": dict(previous),
                    "runtime_balance_unchanged_by_audit": True,
                })
                del audit[:-100]
        root["bnb"] = evidence
        return evidence

    persisted = state_manager.atomic_update(persist)
    if isinstance(persisted, dict) and persisted.get("status") == "PASS":
        return persisted
    return persisted if isinstance(persisted, dict) else {"status": "EVIDENCE_PERSIST_FAILED"}
