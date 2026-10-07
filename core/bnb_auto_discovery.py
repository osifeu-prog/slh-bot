"""Automatic discovery and controlled reconciliation of an already-sent BNB canary.

The discovery provider is used only to find a candidate transaction hash.
Canonical settlement verification still runs through the configured BSC RPC and
the existing owner-only canary path. This module never signs or broadcasts.
"""
from __future__ import annotations

from datetime import datetime, timezone
import requests
from web3 import Web3

import state_manager
from core.authority import is_owner
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
HANDOFF_WINDOW_SECONDS = 12 * 60
RPC_BATCH_SIZE = 100


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


def _latest_handoff_timestamp(uid: str) -> int | None:
    db = state_manager.load_db()
    rows = db.get("wallet_handoffs", {}) if isinstance(db, dict) else {}
    candidates = []
    if isinstance(rows, dict):
        for row in rows.values():
            if not isinstance(row, dict) or str(row.get("uid") or "") != str(uid):
                continue
            raw = str(row.get("created_at") or "").strip()
            if not raw:
                continue
            try:
                candidates.append(int(datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()))
            except (TypeError, ValueError):
                continue
    return max(candidates) if candidates else None


def _rpc_json(w3: Web3, method: str, params: list) -> object:
    provider = w3.provider
    response = requests.post(
        provider.endpoint_uri,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=8,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        error = payload["error"]
        raise ValueError(f"RPC_{error.get('code')}: {error.get('message')}")
    return payload.get("result")


def _block_timestamp(w3: Web3, block_number: int) -> int:
    result = _rpc_json(w3, "eth_getBlockByNumber", [hex(int(block_number)), False])
    if not isinstance(result, dict):
        raise ValueError("BSC_RPC_BLOCK_NOT_FOUND")
    return int(str(result.get("timestamp") or "0"), 16)


def _estimate_block_range(w3: Web3, target_ts: int, window_seconds: int) -> tuple[int, int]:
    latest = int(w3.eth.block_number)
    latest_ts = _block_timestamp(w3, latest)
    if latest_ts <= 0 or target_ts > latest_ts:
        return latest, latest
    sample_block = max(0, latest - 1000)
    sample_ts = _block_timestamp(w3, sample_block)
    seconds_per_block = max(0.25, (latest_ts - sample_ts) / max(1, latest - sample_block))
    center = int(latest - max(0, latest_ts - target_ts) / seconds_per_block)
    half = int(window_seconds / seconds_per_block) + 12
    return max(0, center - half), min(latest, center + half)


def _rpc_find_exact_transfers(w3: Web3, sender: str, treasury: str, target_ts: int) -> list[dict]:
    start, end = _estimate_block_range(w3, target_ts, HANDOFF_WINDOW_SECONDS)
    candidates = []
    for batch_start in range(start, end + 1, RPC_BATCH_SIZE):
        batch_end = min(end, batch_start + RPC_BATCH_SIZE - 1)
        payload = [
            {
                "jsonrpc": "2.0",
                "id": block,
                "method": "eth_getBlockByNumber",
                "params": [hex(block), True],
            }
            for block in range(batch_start, batch_end + 1)
        ]
        response = requests.post(
            w3.provider.endpoint_uri,
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        results = response.json()
        if not isinstance(results, list):
            raise ValueError("BSC_RPC_BATCH_INVALID_RESPONSE")
        for item in results:
            block = item.get("result") if isinstance(item, dict) else None
            if not isinstance(block, dict):
                continue
            block_number = int(str(block.get("number") or "0x0"), 16)
            block_ts = int(str(block.get("timestamp") or "0x0"), 16)
            for tx in block.get("transactions") or []:
                if not isinstance(tx, dict):
                    continue
                tx_from = str(tx.get("from") or "")
                tx_to = str(tx.get("to") or "")
                try:
                    value_wei = int(str(tx.get("value") or "0x0"), 16)
                except (TypeError, ValueError):
                    continue
                if (
                    tx_from.lower() == sender.lower()
                    and tx_to.lower() == treasury.lower()
                    and value_wei == TARGET_AMOUNT_WEI
                ):
                    candidates.append({
                        "tx_hash": str(tx.get("hash") or ""),
                        "timestamp": block_ts,
                        "block": block_number,
                        "amount_wei": value_wei,
                        "from": tx_from,
                        "to": tx_to,
                    })
    return candidates


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

    sender_raw = str(binding.get("address") or "").strip()
    treasury_raw = str(cfg.get("treasury_wallet") or "").strip()
    if not sender_raw:
        raise ValueError("BNB_WALLET_NOT_VERIFIED")
    if not treasury_raw:
        raise ValueError("BNB_TREASURY_MISSING")

    sender = w3.to_checksum_address(sender_raw)
    treasury = w3.to_checksum_address(treasury_raw)

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
        handoff_ts = _latest_handoff_timestamp(uid)
        if handoff_ts:
            rpc_rows = _rpc_find_exact_transfers(w3, sender, treasury, handoff_ts)
            rpc_rows = [row for row in rpc_rows if row.get("tx_hash")]
            rpc_rows.sort(key=lambda item: (abs(item["timestamp"] - handoff_ts), item["tx_hash"].lower()))
            unsettled_rpc = [
                row for row in rpc_rows
                if f"bnb:deposit:{row['tx_hash'].lower()}" not in ledger_keys
            ]
            if len(unsettled_rpc) > 1:
                return {
                    "status": "AMBIGUOUS",
                    "scope": "read_only_discovery",
                    "provider": "BSC_RPC_HANDOFF_WINDOW",
                    "uid": uid,
                    "sender": sender,
                    "treasury": treasury,
                    "amount_wei": TARGET_AMOUNT_WEI,
                    "handoff_timestamp": handoff_ts,
                    "candidates": rpc_rows,
                }
            if unsettled_rpc or rpc_rows:
                candidate = (unsettled_rpc or rpc_rows)[0]
                return {
                    "status": "FOUND",
                    "scope": "read_only_discovery",
                    "provider": "BSC_RPC_HANDOFF_WINDOW",
                    "uid": uid,
                    "sender": sender,
                    "treasury": treasury,
                    "amount_wei": TARGET_AMOUNT_WEI,
                    "handoff_timestamp": handoff_ts,
                    "candidate": candidate,
                    "candidates": rpc_rows,
                }
        return {
            "status": "NOT_FOUND",
            "scope": "read_only_discovery",
            "uid": uid,
            "sender": sender,
            "treasury": treasury,
            "amount_wei": TARGET_AMOUNT_WEI,
            "candidates": [],
            "handoff_timestamp": _latest_handoff_timestamp(uid),
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
