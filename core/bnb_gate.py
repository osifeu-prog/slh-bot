"""BNB / BSC deposit gate and readiness contract.

The operator flag alone is never enough to open settlement. The live gate is
fail-closed until the BSC network, RPC and treasury are configured correctly.
"""
from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime
from pathlib import Path

from core.binance_connector import get_bsc_config
from core.bsc_address_policy import is_quarantined_bsc_address
import state_manager

CLOSED_MESSAGE = "⛔️ הפקדות BNB/SLH סגורות כרגע. אל תשלח עד להודעה."


def _effective_config(db=None) -> dict:
    cfg = dict(get_bsc_config())
    if db is None:
        try:
            db = state_manager.load_db()
        except Exception:
            return cfg
    overrides = db.get("bsc_settings") if isinstance(db, dict) else None
    if isinstance(overrides, dict):
        cfg.update(overrides)
    return cfg


def bnb_readiness(db=None) -> dict:
    cfg = _effective_config(db)
    reasons: list[str] = []
    chain_id = cfg.get("chain_id")
    if int(chain_id or 0) != 56:
        reasons.append("BSC_CHAIN_ID_NOT_56")

    rpc = str(cfg.get("rpc") or "").strip()
    if not rpc:
        reasons.append("BSC_RPC_MISSING")

    treasury = str(cfg.get("treasury_wallet") or "").strip()
    if not treasury:
        reasons.append("BNB_TREASURY_MISSING")
    elif is_quarantined_bsc_address(treasury):
        reasons.append("BNB_TREASURY_QUARANTINED_ZUZ")

    canonical_treasury = str(os.getenv("SLH_BSC_CANONICAL_TREASURY", "")).strip()
    if not canonical_treasury:
        reasons.append("BNB_CANONICAL_TREASURY_MISSING")
    elif is_quarantined_bsc_address(canonical_treasury):
        reasons.append("BNB_CANONICAL_TREASURY_QUARANTINED_ZUZ")
    elif canonical_treasury.lower() != treasury.lower():
        reasons.append("BNB_CANONICAL_TREASURY_MISMATCH")

    try:
        confirmations = int(cfg.get("confirmations") or 15)
    except (TypeError, ValueError):
        confirmations = 0
    if confirmations < 1:
        reasons.append("BNB_CONFIRMATIONS_INVALID")

    flag_open = os.getenv("BNB_DEPOSITS_OPEN", "0").strip() == "1"
    return {
        "flag_open": flag_open,
        "ready": not reasons,
        "effective_open": flag_open and not reasons,
        "chain_id": int(chain_id or 0),
        "network": cfg.get("network", "bsc"),
        "treasury_configured": bool(treasury),
        "confirmations_required": confirmations,
        "reasons": reasons,
    }




def _empirical_settlement_evidence() -> dict | None:
    try:
        db = state_manager.load_db()
    except Exception:
        return None
    evidence = db.get("settlement_evidence", {}) if isinstance(db, dict) else {}
    bnb = evidence.get("bnb") if isinstance(evidence, dict) else None
    return bnb if isinstance(bnb, dict) else None

def _empirical_evidence_shape_valid(empirical: dict | None) -> bool:
    """Reject incomplete or internally inconsistent persisted smoke evidence."""
    if not isinstance(empirical, dict) or empirical.get("status") != "PASS":
        return False
    tx_hash = str(empirical.get("tx_hash") or "").strip()
    if not re.fullmatch(r"0x[0-9a-fA-F]{64}", tx_hash):
        return False
    try:
        observed_at = datetime.fromisoformat(
            str(empirical.get("observed_at") or "").replace("Z", "+00:00")
        )
        if observed_at.tzinfo is None:
            return False
        amount_wei = int(empirical.get("amount_wei"))
        confirmations = int(empirical.get("confirmations"))
        ledger_count = int(empirical.get("ledger_entries_for_idempotency_key"))
        credits = float(empirical.get("credits"))
        before = float(empirical.get("balance_before"))
        after = float(empirical.get("balance_after"))
        replay_after = float(empirical.get("replay_balance_after"))
    except (TypeError, ValueError, OverflowError):
        return False
    checks = empirical.get("checks")
    required_checks = (
        "wallet_binding", "tx_verification", "idempotency",
        "atomic_ledger", "reconciliation",
    )
    if not isinstance(checks, dict) or any(checks.get(key) is not True for key in required_checks):
        return False
    numeric = (credits, before, after, replay_after)
    if not all(math.isfinite(value) for value in numeric):
        return False
    if amount_wei <= 0 or confirmations < 1 or ledger_count != 1 or credits <= 0:
        return False
    if empirical.get("from_bound_wallet") is not True or empirical.get("gate_remained_closed") is not True:
        return False
    if not str(empirical.get("uid") or "").strip() or not str(empirical.get("to_treasury") or "").strip():
        return False
    if abs((before + credits) - after) > 1e-9 or abs(replay_after - after) > 1e-9:
        return False
    # The smoke's conversion contract is 1,000 internal credits per BNB.
    expected_credits = (amount_wei / 10**18) * 1000
    if abs(expected_credits - credits) > max(1e-9, abs(expected_credits) * 1e-9):
        return False
    return True


def _empirical_evidence_revalidated(empirical: dict | None, gate: dict) -> bool:
    """Re-check the persisted proof against current wallet, chain and ledger state."""
    if not _empirical_evidence_shape_valid(empirical):
        return False
    try:
        from core.deposit_monitor import verify_bnb_deposit
        from core.wallet_binding import get_binding

        uid = str(empirical["uid"])
        tx_hash = str(empirical["tx_hash"])
        verified = verify_bnb_deposit(tx_hash)
        binding = get_binding(uid)
        if not verified.get("ok") or not binding:
            return False
        if str(verified.get("tx_hash") or "").lower() != tx_hash.lower():
            return False
        if str(verified.get("from") or "").lower() != str(binding.get("address") or "").lower():
            return False
        if str(verified.get("to") or "").lower() != str(empirical.get("to_treasury") or "").lower():
            return False
        if str(verified.get("to") or "").lower() != str(gate.get("treasury_wallet") or "").lower():
            return False
        if int(verified.get("amount_wei") or 0) != int(empirical.get("amount_wei") or 0):
            return False
        required_confirmations = int(
            gate.get("confirmations_required", gate.get("confirmations", 15)) or 15
        )
        if int(verified.get("confirmations") or 0) < required_confirmations:
            return False
        db = state_manager.load_db()
        ledger = db.get("ledger", []) if isinstance(db, dict) else []
        key = f"bnb:deposit:{tx_hash.lower()}"
        matching = [
            entry for entry in ledger
            if isinstance(entry, dict)
            and isinstance(entry.get("meta"), dict)
            and entry["meta"].get("idempotency_key") == key
        ]
        if len(matching) != 1:
            return False
        entry = matching[0]
        if str(entry.get("uid") or "") != uid:
            return False
        if entry.get("reason") != "bnb:deposit":
            return False
        if abs(float(entry.get("amount", 0)) - float(empirical["credits"])) > 1e-9:
            return False
        if abs(float(entry.get("before", 0)) - float(empirical["balance_before"])) > 1e-9:
            return False
        if abs(float(entry.get("after", 0)) - float(empirical["balance_after"])) > 1e-9:
            return False
        return True
    except Exception:
        return False


def bnb_opening_evidence() -> dict:
    """Read-only evidence for whether BNB could safely be opened.

    This function never changes the operator gate. It combines static gate
    configuration with a live RPC snapshot and explicitly reports the
    remaining empirical settlement proof as pending until a controlled,
    authorized reconciliation has been completed.
    """
    gate = bnb_readiness()
    evidence = {
        "status": "BLOCKED",
        "ready_to_open": False,
        "scope": "read_only",
        "gate_open": False,
        "checks": {},
        "blockers": [],
        "warnings": [],
    }

    evidence["checks"]["configured_chain"] = {
        "status": "PASS" if gate.get("chain_id") == 56 else "FAIL",
        "chain_id": gate.get("chain_id"),
    }
    evidence["checks"]["rpc_configured"] = {
        "status": "PASS" if gate.get("ready") and "BSC_RPC_MISSING" not in gate.get("reasons", []) else "FAIL",
    }
    evidence["checks"]["configured_treasury"] = {
        "status": "PASS" if gate.get("treasury_configured") and "BNB_TREASURY_QUARANTINED_ZUZ" not in gate.get("reasons", []) else "FAIL",
    }
    evidence["checks"]["canonical_treasury"] = {
        "status": "PASS" if "BNB_CANONICAL_TREASURY_MISSING" not in gate.get("reasons", [])
        and "BNB_CANONICAL_TREASURY_MISMATCH" not in gate.get("reasons", [])
        and "BNB_CANONICAL_TREASURY_QUARANTINED_ZUZ" not in gate.get("reasons", [])
        else "FAIL",
    }
    evidence["checks"]["confirmations"] = {
        "status": "PASS" if gate.get("confirmations_required", 0) >= 1 else "FAIL",
        "required": gate.get("confirmations_required"),
    }

    try:
        from core.deposit_monitor import get_onchain_status
        live = get_onchain_status()
    except Exception as exc:
        live = {"ok": False, "error": type(exc).__name__}

    evidence["live_rpc"] = {
        "status": "PASS" if live.get("ok") else "FAIL",
        "chain_id": live.get("chain_id"),
        "block": live.get("block"),
        "treasury_wallet": live.get("treasury_wallet"),
        "network": live.get("network"),
    }

    if live.get("ok"):
        if int(live.get("chain_id") or 0) != 56:
            evidence["blockers"].append("LIVE_BSC_CHAIN_ID_NOT_56")
        configured = str(gate.get("chain_id") or "")
        if configured != "56":
            evidence["blockers"].append("CONFIGURED_BSC_CHAIN_ID_NOT_56")
        configured_treasury = str(live.get("treasury_wallet") or "").lower()
        canonical = str(os.getenv("SLH_BSC_CANONICAL_TREASURY", "")).strip().lower()
        if canonical and configured_treasury != canonical:
            evidence["blockers"].append("LIVE_TREASURY_CANONICAL_MISMATCH")
    else:
        evidence["blockers"].append("LIVE_BSC_RPC_UNVERIFIED")

    empirical = _empirical_settlement_evidence()
    empirical_valid = _empirical_evidence_revalidated(empirical, _effective_config())
    evidence["gate_open"] = bool(gate.get("effective_open") and empirical_valid)
    if empirical_valid:
        for check in (
            "wallet_binding",
            "tx_verification",
            "idempotency",
            "atomic_ledger",
            "reconciliation",
        ):
            evidence["checks"][check] = {"status": "PASS", "source": "revalidated_state_and_chain"}
        evidence["empirical_settlement"] = {
            "status": "PASS",
            "tx_hash": empirical.get("tx_hash"),
            "observed_at": empirical.get("observed_at"),
        }
        evidence["next_action"] = "operator_may_review_bnb_gate_opening"
    else:
        for check in (
            "wallet_binding",
            "tx_verification",
            "idempotency",
            "atomic_ledger",
            "reconciliation",
        ):
            evidence["checks"][check] = {"status": "PENDING_EMPIRICAL"}
        evidence["warnings"].append("empirical_settlement_reconciliation_pending_or_invalid")
        evidence["next_action"] = "controlled_empirical_reconciliation_before_opening"

    if evidence["blockers"]:
        return evidence
    evidence["status"] = "READY_TO_OPEN" if all(
        item["status"] == "PASS"
        for item in evidence["checks"].values()
        if isinstance(item, dict) and "status" in item
    ) else "BLOCKED"
    evidence["ready_to_open"] = evidence["status"] == "READY_TO_OPEN"
    return evidence


def bnb_deposits_open() -> bool:
    """Public BNB deposits require both the operator flag and revalidated proof.

    Owner-canary settlement remains separately authorized while the public
    gate is closed; a persisted status=PASS record alone can never open it.
    """
    gate = bnb_readiness()
    if not bool(gate.get("effective_open")):
        return False
    empirical = _empirical_settlement_evidence()
    return _empirical_evidence_revalidated(empirical, _effective_config())


def bnb_settlement_allowed(uid, db=None) -> bool:
    """Allow normal settlement only when OPEN, or owner canary while the gate stays closed.

    The canary is intentionally restricted to the configured UID and the same
    readiness contract used by the production gate. It never opens the gate.
    """
    uid = str(uid)
    if bnb_deposits_open():
        return True

    canary_uid = str(os.getenv("BNB_DEPOSITS_CANARY_UID", "")).strip()
    return bool(
        canary_uid
        and uid == canary_uid
        and bnb_readiness(db).get("ready")
    )
