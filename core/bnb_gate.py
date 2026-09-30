"""BNB / BSC deposit gate and readiness contract.

The operator flag alone is never enough to open settlement. The live gate is
fail-closed until the BSC network, RPC and treasury are configured correctly.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from core.binance_connector import get_bsc_config

CLOSED_MESSAGE = "⛔️ הפקדות BNB/SLH סגורות כרגע. אל תשלח עד להודעה."


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

    # These checks intentionally remain pending without a live-money operation.
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
