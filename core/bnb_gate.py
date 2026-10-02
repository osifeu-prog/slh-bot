"""BNB / BSC deposit gate and readiness contract.

The operator flag alone is never enough to open settlement. The live gate is
fail-closed until the BSC network, RPC and treasury are configured correctly.
"""
from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path

from core.binance_connector import get_bsc_config

CLOSED_MESSAGE = "⛔️ הפקדות BNB/SLH סגורות כרגע. אל תשלח עד להודעה."

EMPIRICAL_RECONCILIATIONS_KEY = "bnb_empirical_reconciliations"


def _effective_db() -> dict:
    path = Path("state/db.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _effective_config() -> dict:
    cfg = dict(get_bsc_config())
    path = Path("state/db.json")
    try:
        db = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return cfg
    overrides = db.get("bsc_settings") if isinstance(db, dict) else None
    if isinstance(overrides, dict):
        cfg.update(overrides)
    return cfg


def record_bnb_empirical_reconciliation(uid: str, tx_hash: str) -> dict:
    """Record a completed, owner-authorized live BNB settlement proof.

    This does not open the gate and does not credit balances. It requires an
    already-settled BNB claim whose sender matches the currently verified
    wallet, whose transaction has the configured confirmations, and whose
    canonical ledger entry is present exactly once with the exact conversion.
    """
    uid = str(uid).strip()
    tx_hash = str(tx_hash or "").strip()
    if not uid or not tx_hash:
        raise ValueError("INVALID_EMPIRICAL_RECONCILIATION_INPUT")

    from core.deposit_monitor import verify_bnb_deposit
    from core.wallet_binding import get_binding

    binding = get_binding(uid)
    if not binding:
        raise ValueError("BNB_WALLET_NOT_VERIFIED")

    verified = verify_bnb_deposit(tx_hash)
    if not verified.get("ok"):
        raise ValueError(str(verified.get("error") or "BNB_TX_NOT_VERIFIED"))

    sender = str(verified.get("from") or "")
    bound = str(binding.get("address") or "")
    if not sender or not bound or sender.lower() != bound.lower():
        raise ValueError("BNB_TX_SENDER_NOT_BOUND_WALLET")

    idempotency_key = f"bnb:deposit:{tx_hash.lower()}"
    db = _effective_db()
    matching = [
        entry for entry in db.get("ledger", [])
        if isinstance(entry, dict)
        and str(entry.get("reason")) == "bnb:deposit"
        and str((entry.get("meta") or {}).get("idempotency_key")) == idempotency_key
        and str(entry.get("uid")) == uid
    ]
    if len(matching) != 1:
        raise ValueError("EMPIRICAL_LEDGER_RECONCILIATION_FAILED")

    ledger_entry = matching[0]
    credits = Decimal(str(ledger_entry.get("amount", "0")))
    expected = (
        Decimal(int(verified.get("amount_wei", 0)))
        * Decimal("1000")
        / Decimal(10**18)
    )
    if credits != expected:
        raise ValueError("EMPIRICAL_CREDIT_CONVERSION_MISMATCH")

    canonical = str(os.getenv("SLH_BSC_CANONICAL_TREASURY", "")).strip().lower()
    configured = str(verified.get("to") or "").strip().lower()
    if not canonical or configured != canonical:
        raise ValueError("EMPIRICAL_TREASURY_MISMATCH")

    record = {
        "status": "PASS",
        "schema_version": 1,
        "uid": uid,
        "tx_hash": tx_hash.lower(),
        "chain_id": 56,
        "treasury": configured,
        "sender": sender.lower(),
        "amount_wei": int(verified.get("amount_wei", 0)),
        "amount_bnb": str(verified.get("amount_bnb")),
        "credits": str(credits),
        "confirmations": int(verified.get("confirmations", 0)),
        "required_confirmations": int(verified.get("required_confirmations", 15)),
        "ledger_entries": 1,
        "idempotency_key": idempotency_key,
        "deployment_commit": os.getenv("RAILWAY_GIT_COMMIT_SHA", "unknown"),
    }

    import state_manager

    def mutate(db_state):
        records = db_state.setdefault(EMPIRICAL_RECONCILIATIONS_KEY, {})
        existing = records.get(tx_hash.lower())
        if existing is not None:
            if str(existing.get("uid")) != uid:
                raise ValueError("EMPIRICAL_TX_ALREADY_BOUND")
            return {**existing, "idempotent": True}

        current_matching = [
            entry for entry in db_state.get("ledger", [])
            if isinstance(entry, dict)
            and str(entry.get("reason")) == "bnb:deposit"
            and str((entry.get("meta") or {}).get("idempotency_key")) == idempotency_key
            and str(entry.get("uid")) == uid
        ]
        if len(current_matching) != 1:
            raise ValueError("EMPIRICAL_LEDGER_RECONCILIATION_FAILED")
        records[tx_hash.lower()] = record
        return {**record, "idempotent": False}

    return state_manager.atomic_update(mutate)


def bnb_readiness() -> dict:
    cfg = _effective_config()
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

    canonical_treasury = str(os.getenv("SLH_BSC_CANONICAL_TREASURY", "")).strip()
    if not canonical_treasury:
        reasons.append("BNB_CANONICAL_TREASURY_MISSING")
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
        "gate_open": bool(gate.get("effective_open")),
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
        "status": "PASS" if gate.get("treasury_configured") else "FAIL",
    }
    evidence["checks"]["canonical_treasury"] = {
        "status": "PASS" if "BNB_CANONICAL_TREASURY_MISSING" not in gate.get("reasons", [])
        and "BNB_CANONICAL_TREASURY_MISMATCH" not in gate.get("reasons", [])
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

    db = _effective_db()
    empirical_records = db.get(EMPIRICAL_RECONCILIATIONS_KEY, {})
    empirical = None
    if isinstance(empirical_records, dict):
        for candidate in empirical_records.values():
            if not isinstance(candidate, dict):
                continue
            if str(candidate.get("status")).upper() != "PASS":
                continue
            if int(candidate.get("chain_id") or 0) != 56:
                continue
            if str(candidate.get("treasury") or "").lower() != str(
                os.getenv("SLH_BSC_CANONICAL_TREASURY", "")
            ).strip().lower():
                continue
            empirical = candidate
            break

    if empirical:
        evidence["checks"]["wallet_binding"] = {"status": "PASS"}
        evidence["checks"]["tx_verification"] = {
            "status": "PASS",
            "confirmations": empirical.get("confirmations"),
        }
        evidence["checks"]["idempotency"] = {
            "status": "PASS",
            "ledger_entries": empirical.get("ledger_entries"),
            "idempotency_key_present": bool(empirical.get("idempotency_key")),
        }
        evidence["checks"]["atomic_ledger"] = {
            "status": "PASS",
            "ledger_entries": empirical.get("ledger_entries"),
        }
        evidence["checks"]["reconciliation"] = {
            "status": "PASS",
            "tx_hash_present": bool(empirical.get("tx_hash")),
        }
        evidence["empirical_reconciliation"] = {
            "status": "PASS",
            "uid": empirical.get("uid"),
            "tx_hash": empirical.get("tx_hash"),
            "deployment_commit": empirical.get("deployment_commit", "unknown"),
        }
        evidence["next_action"] = "operator_can_enable_bnb_settlement_after_release_review"
    else:
        evidence["checks"]["wallet_binding"] = {"status": "PENDING_EMPIRICAL"}
        evidence["checks"]["tx_verification"] = {"status": "PENDING_EMPIRICAL"}
        evidence["checks"]["idempotency"] = {"status": "PENDING_EMPIRICAL"}
        evidence["checks"]["atomic_ledger"] = {"status": "PENDING_EMPIRICAL"}
        evidence["checks"]["reconciliation"] = {"status": "PENDING_EMPIRICAL"}
        evidence["warnings"].append("empirical_settlement_reconciliation_pending")
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
    return bool(bnb_readiness()["effective_open"])
