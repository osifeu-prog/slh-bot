"""Automatic discovery and controlled reconciliation of an already-sent BNB canary.

The discovery provider is used only to find a candidate transaction hash.
Canonical settlement verification still runs through the configured BSC RPC and
the existing owner-only canary path. This module never signs or broadcasts.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os

import requests
from web3 import Web3

import state_manager
from core.authority import is_owner
from core.bnb_deposit_service import settle_bnb_deposit
from core.bnb_gate import bnb_deposits_open, bnb_readiness, bnb_settlement_allowed
from core.bnb_empirical_smoke import run as run_empirical_smoke
from core.binance_connector import get_bsc_config
from core.deposit_monitor import verify_bnb_deposit
from core.wallet_binding import get_binding

BINPLORER_URL = "https://api.binplorer.com"
BINPLORER_KEY = "freekey"
DEFAULT_LIMIT = 100
TARGET_AMOUNT_WEI = 10**16
MAX_AGE_SECONDS = 30 * 24 * 60 * 60


def _config() -> dict:
    cfg = dict(get_bsc_config())
    db = state_manager.load_db()
    overrides = db.get("bsc_settings") if isinstance(db, dict) else None
    if isinstance(overrides, dict):
        cfg.update(overrides)
    return cfg


def _ledger_keys() -> set[str]:
    db = state_manager.load_db()
    return {
        str(entry.get("meta", {}).get("idempotency_key") or "").strip().lower()
        for entry in db.get("ledger", [])
        if isinstance(entry, dict)
    }


def _parse_int(value) -> int:
    raw = str(value or "").strip()
    if not raw:
        return 0
    return int(raw, 16) if raw.lower().startswith("0x") else int(raw)


def discover_bnb_transfer(uid: str, *, limit: int = DEFAULT_LIMIT) -> dict:
    """Read-only discovery of exact native BNB transfers for a bound wallet."""
    uid = str(uid)
    binding = get_binding(uid)
    if not binding:
        raise ValueError("BNB_WALLET_NOT_VERIFIED")

    cfg = _config()
    w3 = Web3(Web3.HTTPProvider(cfg["rpc"]))
    if int(w3.eth.chain_id) != 56:
        raise ValueError("BSC_CHAIN_ID_NOT_56")

    sender = w3.to_checksum_address(str(binding.get("address") or ""))
    treasury = w3.to_checksum_address(str(cfg.get("treasury_wallet") or ""))
    if not treasury:
        raise ValueError("BNB_TREASURY_MISSING")

    # Ask an indexer only for transaction discovery. The returned candidate is
    # re-checked by verify_bnb_deposit against the canonical BSC RPC below.
    response = requests.get(
        f"{BINPLORER_URL}/getAddressTransactions/{sender}",
        params={
            "apiKey": BINPLORER_KEY,
            "limit": max(1, min(int(limit), DEFAULT_LIMIT)),
            "showZeroValues": "false",
        },
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError("BNB_DISCOVERY_INVALID_INDEX_RESPONSE")

    now = int(datetime.now(timezone.utc).timestamp())
    rows = []
    ledger_keys = _ledger_keys()

    for row in data:
        if not isinstance(row, dict):
            continue
        try:
            raw_value = _parse_int(row.get("rawValue"))
        except (TypeError, ValueError):
            continue

        row_from = str(row.get("from") or "").strip()
        row_to = str(row.get("to") or "").strip()
        tx_hash = str(row.get("hash") or "").strip()
        try:
            ts = int(row.get("timestamp") or 0)
        except (TypeError, ValueError):
            ts = 0

        if not tx_hash or not row_from or not row_to:
            continue
        if row_from.lower() != sender.lower():
            continue
        if row_to.lower() != treasury.lower():
            continue
        if raw_value != TARGET_AMOUNT_WEI:
            continue
        if row.get("success") is False:
            continue
        if ts and now - ts > MAX_AGE_SECONDS:
            continue

        key = f"bnb:deposit:{tx_hash.lower()}"
        rows.append({
            "tx_hash": tx_hash,
            "timestamp": ts,
            "amount_wei": raw_value,
            "from": row_from,
            "to": row_to,
            "already_recorded": key in ledger_keys,
        })

    rows.sort(key=lambda item: (item["timestamp"], item["tx_hash"].lower()), reverse=True)

    if not rows:
        return {
            "status": "NOT_FOUND",
            "scope": "read_only_discovery",
            "uid": uid,
            "sender": sender,
            "treasury": treasury,
            "amount_wei": TARGET_AMOUNT_WEI,
            "candidates": [],
        }

    unsettled = [row for row in rows if not row["already_recorded"]]
    if len(unsettled) > 1:
        return {
            "status": "AMBIGUOUS",
            "scope": "read_only_discovery",
            "uid": uid,
            "sender": sender,
            "treasury": treasury,
            "amount_wei": TARGET_AMOUNT_WEI,
            "candidates": rows,
        }

    candidate = unsettled[0] if len(unsettled) == 1 else rows[0]
    return {
        "status": "FOUND",
        "scope": "read_only_discovery",
        "uid": uid,
        "sender": sender,
        "treasury": treasury,
        "amount_wei": TARGET_AMOUNT_WEI,
        "candidate": candidate,
        "candidates": rows,
    }


def run_owner_auto_smoke(uid: str) -> dict:
    """Discover and reconcile the existing 0.01 BNB canary, fail-closed."""
    uid = str(uid)
    if not is_owner(uid):
        raise ValueError("BNB_EMPIRICAL_SMOKE_OWNER_ONLY")
    if bnb_deposits_open():
        raise ValueError("BNB_EMPIRICAL_SMOKE_REQUIRES_CLOSED_GATE")
    if not bnb_settlement_allowed(uid):
        raise ValueError("BNB_EMPIRICAL_SMOKE_NOT_AUTHORIZED")

    evidence = state_manager.load_db().get("settlement_evidence", {}).get("bnb")
    if isinstance(evidence, dict) and evidence.get("status") == "PASS":
        return {"status": "ALREADY_PASS", "evidence": evidence}

    discovered = discover_bnb_transfer(uid)
    if discovered["status"] != "FOUND":
        return discovered

    tx_hash = discovered["candidate"]["tx_hash"]
    verified = verify_bnb_deposit(tx_hash)
    if not verified.get("ok"):
        if verified.get("error") == "INSUFFICIENT_CONFIRMATIONS":
            return {
                "status": "WAITING_FOR_CONFIRMATIONS",
                "tx_hash": tx_hash,
                "confirmations": verified.get("confirmations"),
                "required_confirmations": verified.get("required_confirmations"),
                "block": verified.get("block"),
                "discovery": discovered,
            }
        raise ValueError(str(verified.get("error") or "BNB_TX_NOT_VERIFIED"))

    # Re-check the canonical facts immediately before any ledger mutation.
    bound = str(get_binding(uid).get("address") or "")
    if str(verified.get("from") or "").lower() != bound.lower():
        raise ValueError("BNB_TX_SENDER_NOT_BOUND_WALLET")
    if str(verified.get("to") or "").lower() != discovered["treasury"].lower():
        raise ValueError("BNB_TX_TREASURY_MISMATCH")
    if int(verified.get("amount_wei") or 0) != TARGET_AMOUNT_WEI:
        raise ValueError("BNB_TX_AMOUNT_MISMATCH")

    result = run_empirical_smoke(uid, tx_hash)
    return {
        **result,
        "discovery": {
            "provider": "Binplorer",
            "scope": "discovery_only",
            "candidate_count": len(discovered["candidates"]),
        },
    }
