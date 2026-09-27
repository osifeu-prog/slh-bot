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


def bnb_deposits_open() -> bool:
    return bool(bnb_readiness()["effective_open"])
