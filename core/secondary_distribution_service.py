"""User-signed on-chain SLH distribution for an approved secondary wallet.

This service prepares and verifies ERC-20 transfers from an OWNER-approved
secondary distribution wallet. The server never signs or broadcasts a
transaction and never stores a private key.

Preparation creates a short-lived pending request so per-transaction and daily
limits cannot be bypassed by preparing several transactions concurrently.
Completed daily usage is counted from verified on-chain receipts.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from web3 import Web3

import state_manager
from core.distribution_wallet_registry import (
    AUDIT_KEY,
    REGISTRY_KEY,
    _bsc_config,
    _limit,
)
from core.wallet_binding import get_binding

PENDING_KEY = "secondary_distribution_pending"
REQUEST_TTL_SECONDS = 600
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
TRANSFER_TOPIC = Web3.keccak(text="Transfer(address,address,uint256)").hex()
ERC20_TRANSFER_SELECTOR = "a9059cbb"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _parse_amount(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("INVALID_AMOUNT") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("INVALID_AMOUNT")
    return amount


def _checksum(value: Any, field: str) -> str:
    raw = str(value or "").strip()
    if not raw or not Web3.is_address(raw):
        raise ValueError(f"INVALID_{field.upper()}_ADDRESS")
    address = Web3.to_checksum_address(raw)
    if address == ZERO_ADDRESS:
        raise ValueError(f"INVALID_{field.upper()}_ADDRESS")
    return address


def _client(cfg: dict[str, Any]) -> Web3:
    rpc = str(cfg.get("rpc") or "").strip()
    if not rpc:
        raise ValueError("BSC_RPC_NOT_CONFIGURED")
    web3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 8}))
    if not web3.is_connected():
        raise ValueError("BSC_RPC_UNAVAILABLE")
    chain_id = int(web3.eth.chain_id)
    if chain_id != 56:
        raise ValueError("BSC_CHAIN_ID_NOT_56")
    return web3

def _transaction_sender(web3: Web3, tx_hash: str) -> str:
    """Read the broadcast transaction sender, treating propagation lag as retryable."""
    try:
        tx = web3.eth.get_transaction(tx_hash)
    except TransactionNotFound as exc:
        raise ValueError("TRANSACTION_NOT_FOUND_RETRYABLE") from exc
    return str(tx.get("from") or "")


def _encode_transfer(recipient: str, raw_amount: int) -> str:
    return (
        "0x"
        + ERC20_TRANSFER_SELECTOR
        + recipient[2:].lower().zfill(64)
        + hex(int(raw_amount))[2:].zfill(64)
    )


def _token_contract(web3: Web3, address: str):
    return web3.eth.contract(
        address=_checksum(address, "token"),
        abi=[
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function",
            },
        ],
    )


def _utc_day(value: datetime) -> str:
    return value.date().isoformat()


def _completed_today(db: dict, uid: str, now: datetime) -> Decimal:
    total = Decimal("0")
    target_day = _utc_day(now)
    rows = db.get(AUDIT_KEY, []) if isinstance(db, dict) else []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        if row.get("event") != "secondary_distribution_confirmed":
            continue
        if str(row.get("uid")) != str(uid):
            continue
        stamp = str(row.get("confirmed_at") or "")
        try:
            day = _utc_day(datetime.fromisoformat(stamp.replace("Z", "+00:00")))
        except (TypeError, ValueError):
            continue
        if day == target_day:
            try:
                total += _parse_amount(row.get("amount_slh"))
            except ValueError:
                continue
    return total


def _active_record(db: dict, uid: str) -> dict:
    record = (db.get(REGISTRY_KEY, {}) or {}).get(str(uid))
    if not isinstance(record, dict) or record.get("status") != "active":
        raise ValueError("SECONDARY_DISTRIBUTION_WALLET_NOT_ACTIVE")
    return record


def _binding_for_uid(uid: str) -> dict:
    binding = get_binding(str(uid))
    if not binding:
        raise ValueError("BNB_WALLET_NOT_VERIFIED")
    return binding


def prepare_secondary_slh_transfer(
    uid: Any,
    recipient: Any,
    amount: Any,
    request_id: Any,
) -> dict[str, Any]:
    """Prepare an approved SLH transfer for the user's external wallet."""
    uid = str(uid)
    request_id = str(request_id or "").strip()
    if not request_id or len(request_id) > 128:
        raise ValueError("INVALID_REQUEST_ID")

    recipient = _checksum(recipient, "recipient")
    amount = _parse_amount(amount)
    binding = _binding_for_uid(uid)
    sender = _checksum(binding.get("address"), "sender")

    db = state_manager.load_db()
    record = _active_record(db, uid)
    if str(record.get("address", "")).lower() != sender.lower():
        raise ValueError("SECONDARY_WALLET_BINDING_MISMATCH")

    limit_mode = str(record.get("limit_mode") or "bounded").strip().lower()
    if limit_mode not in {"bounded", "unbounded"}:
        raise ValueError("INVALID_LIMIT_MODE")

    now = _now()
    if limit_mode == "bounded":
        per_tx = _limit(record.get("per_tx_limit_slh"), "PER_TX_LIMIT")
        daily = _limit(record.get("daily_limit_slh"), "DAILY_LIMIT")
        if amount > per_tx:
            raise ValueError("PER_TX_LIMIT_EXCEEDED")

        completed = _completed_today(db, uid, now)
        pending = db.get(PENDING_KEY, {}) if isinstance(db, dict) else {}
        pending_today = Decimal("0")
        for row in pending.values() if isinstance(pending, dict) else []:
            if not isinstance(row, dict) or str(row.get("uid")) != uid or row.get("status") != "prepared":
                continue
            try:
                created = datetime.fromisoformat(str(row.get("prepared_at")).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                continue
            if created + timedelta(seconds=REQUEST_TTL_SECONDS) < now:
                continue
            if _utc_day(created) == _utc_day(now):
                try:
                    pending_today += _parse_amount(row.get("amount_slh"))
                except ValueError:
                    continue

        if completed + pending_today + amount > daily:
            raise ValueError("DAILY_LIMIT_EXCEEDED")

    cfg = _bsc_config()
    token_address = str(cfg.get("token_contract") or "").strip()
    token = _checksum(token_address, "token")
    web3 = _client(cfg)
    chain_token = _token_contract(web3, token)
    decimals = int(chain_token.functions.decimals().call())
    if decimals < 0 or decimals > 36:
        raise ValueError("TOKEN_DECIMALS_INVALID")

    raw_amount = int(amount * (Decimal(10) ** decimals))
    if raw_amount <= 0:
        raise ValueError("INVALID_AMOUNT")

    balance_raw = int(chain_token.functions.balanceOf(sender).call())
    if raw_amount > balance_raw:
        raise ValueError("INSUFFICIENT_SLH_BALANCE")

    data = _encode_transfer(recipient, raw_amount)
    gas = int(
        web3.eth.estimate_gas(
            {"from": sender, "to": token, "data": data, "value": 0}
        )
    )
    gas_price = int(web3.eth.gas_price)
    bnb_balance = int(web3.eth.get_balance(sender))
    fee = gas * gas_price
    if bnb_balance < fee:
        raise ValueError("INSUFFICIENT_BNB_FOR_GAS")

    expires = now + timedelta(seconds=REQUEST_TTL_SECONDS)

    def mutate(state: dict) -> dict:
        registry = state.get(REGISTRY_KEY, {}) or {}
        current = registry.get(uid)
        if not isinstance(current, dict) or current.get("status") != "active":
            raise ValueError("SECONDARY_DISTRIBUTION_WALLET_NOT_ACTIVE")
        if str(current.get("address", "")).lower() != sender.lower():
            raise ValueError("SECONDARY_WALLET_BINDING_MISMATCH")

        pending_map = state.setdefault(PENDING_KEY, {})
        old = pending_map.get(request_id)
        if old is not None:
            if str(old.get("uid")) != uid:
                raise ValueError("REQUEST_ID_CONFLICT")
            return dict(old)

        fresh_completed = _completed_today(state, uid, now)
        fresh_pending = Decimal("0")
        for row in pending_map.values():
            if not isinstance(row, dict) or str(row.get("uid")) != uid or row.get("status") != "prepared":
                continue
            try:
                created = datetime.fromisoformat(str(row.get("prepared_at")).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                continue
            if created + timedelta(seconds=REQUEST_TTL_SECONDS) < now:
                continue
            if _utc_day(created) == _utc_day(now):
                try:
                    fresh_pending += _parse_amount(row.get("amount_slh"))
                except ValueError:
                    continue
        current_mode = str(current.get("limit_mode") or "bounded").strip().lower()
        if current_mode not in {"bounded", "unbounded"}:
            raise ValueError("INVALID_LIMIT_MODE")
        if current_mode == "bounded" and fresh_completed + fresh_pending + amount > _limit(
            current.get("daily_limit_slh"), "DAILY_LIMIT"
        ):
            raise ValueError("DAILY_LIMIT_EXCEEDED")

        row = {
            "request_id": request_id,
            "uid": uid,
            "chain": "bsc",
            "chain_id": 56,
            "address": sender,
            "recipient": recipient,
            "token_contract": token,
            "amount_slh": str(amount),
            "amount_raw": raw_amount,
            "status": "prepared",
            "prepared_at": _iso(now),
            "expires_at": _iso(expires),
        }
        pending_map[request_id] = row
        return dict(row)

    pending_row = state_manager.atomic_update(mutate)

    return {
        "ok": True,
        "status": "prepared",
        "request_id": request_id,
        "wallet": sender,
        "recipient": recipient,
        "token": token,
        "chain_id": 56,
        "amount_slh": str(amount),
        "amount_raw": raw_amount,
        "decimals": decimals,
        "expires_at": pending_row["expires_at"],
        "tx": {
            "from": sender,
            "to": token,
            "value": "0x0",
            "data": data,
            "gas": hex(gas),
            "gasPrice": hex(gas_price),
        },
        "estimated_fee_raw": fee,
        "balance_raw": balance_raw,
        "bnb_balance_raw": bnb_balance,
        "broadcast": False,
        "custody": False,
    }


def confirm_secondary_slh_transfer(
    uid: Any,
    request_id: Any,
    tx_hash: Any,
) -> dict[str, Any]:
    uid = str(uid)
    request_id = str(request_id or "").strip()
    tx_hash = str(tx_hash or "").strip()
    if not request_id or not tx_hash:
        raise ValueError("INVALID_CONFIRMATION")

    db = state_manager.load_db()
    pending = db.get(PENDING_KEY, {}) if isinstance(db, dict) else {}
    row = pending.get(request_id) if isinstance(pending, dict) else None
    if not isinstance(row, dict) or str(row.get("uid")) != uid:
        raise ValueError("DISTRIBUTION_REQUEST_NOT_FOUND")
    if row.get("status") != "prepared":
        if row.get("status") == "confirmed":
            return {
                "status": "duplicate",
                "request_id": request_id,
                "tx_hash": row.get("tx_hash"),
            }
        raise ValueError("DISTRIBUTION_REQUEST_NOT_PENDING")

    expires = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
    if _now() >= expires:
        raise ValueError("DISTRIBUTION_REQUEST_EXPIRED")

    cfg = _bsc_config()
    web3 = _client(cfg)
    receipt = web3.eth.get_transaction_receipt(tx_hash)
    if not receipt or int(receipt.get("status", 0)) != 1:
        raise ValueError("BSC_TX_FAILED")

    block = int(receipt.get("blockNumber") or 0)
    latest = int(web3.eth.block_number)
    confirmations = max(0, latest - block + 1)
    required = int(cfg.get("confirmations") or 15)
    if confirmations < required:
        raise ValueError("INSUFFICIENT_CONFIRMATIONS")

    sender = _checksum(row.get("address"), "sender")
    recipient = _checksum(row.get("recipient"), "recipient")
    token = _checksum(row.get("token_contract"), "token")
    tx_from = _transaction_sender(web3, tx_hash)
    if tx_from and tx_from.lower() != sender.lower():
        raise ValueError("TX_SENDER_NOT_BOUND_WALLET")

    matches = []
    for log in receipt.get("logs", []):
        try:
            if _checksum(log.get("address"), "token") != token:
                continue
            topics = log.get("topics") or []
            if len(topics) != 3:
                continue
            topic0 = topics[0].hex() if hasattr(topics[0], "hex") else str(topics[0])
            if topic0.lower() != TRANSFER_TOPIC.lower():
                continue
            raw_from = topics[1].hex() if hasattr(topics[1], "hex") else str(topics[1])
            raw_to = topics[2].hex() if hasattr(topics[2], "hex") else str(topics[2])
            event_from = Web3.to_checksum_address("0x" + raw_from[-40:])
            event_to = Web3.to_checksum_address("0x" + raw_to[-40:])
            data_value = log.get("data", "0x0")
            raw_value = int(data_value.hex(), 16) if hasattr(data_value, "hex") else int(str(data_value), 16)
            if event_from.lower() == sender.lower() and event_to.lower() == recipient.lower():
                matches.append(raw_value)
        except (KeyError, TypeError, ValueError):
            continue

    expected_raw = int(row.get("amount_raw") or 0)
    if len(matches) != 1 or matches[0] != expected_raw:
        raise ValueError("DISTRIBUTION_TRANSFER_MISMATCH")

    now = _now()

    def mutate(state: dict) -> dict:
        current_pending = state.setdefault(PENDING_KEY, {}).get(request_id)
        if not isinstance(current_pending, dict) or str(current_pending.get("uid")) != uid:
            raise ValueError("DISTRIBUTION_REQUEST_NOT_FOUND")
        if current_pending.get("status") == "confirmed":
            return {"status": "duplicate", "request_id": request_id, "tx_hash": current_pending.get("tx_hash")}
        if current_pending.get("status") != "prepared":
            raise ValueError("DISTRIBUTION_REQUEST_NOT_PENDING")

        registry = state.setdefault(REGISTRY_KEY, {}).get(uid)
        if not isinstance(registry, dict) or registry.get("status") != "active":
            raise ValueError("SECONDARY_DISTRIBUTION_WALLET_NOT_ACTIVE")
        if str(registry.get("address", "")).lower() != sender.lower():
            raise ValueError("SECONDARY_WALLET_BINDING_MISMATCH")

        current_pending["status"] = "confirmed"
        current_pending["tx_hash"] = tx_hash
        current_pending["confirmed_at"] = _iso(now)
        state.setdefault(AUDIT_KEY, []).append(
            {
                "event": "secondary_distribution_confirmed",
                "uid": uid,
                "address": sender,
                "recipient": recipient,
                "token_contract": token,
                "amount_slh": str(row["amount_slh"]),
                "amount_raw": expected_raw,
                "request_id": request_id,
                "tx_hash": tx_hash,
                "confirmed_at": _iso(now),
                "confirmations": confirmations,
                "funds_moved": True,
                "server_broadcast": False,
                "custody_granted": False,
            }
        )
        return {
            "status": "confirmed",
            "request_id": request_id,
            "tx_hash": tx_hash,
            "amount_slh": row["amount_slh"],
            "recipient": recipient,
            "confirmations": confirmations,
        }

    return state_manager.atomic_update(mutate)


def cancel_secondary_slh_transfer(uid: Any, request_id: Any) -> dict[str, Any]:
    uid = str(uid)
    request_id = str(request_id or "").strip()
    if not request_id:
        raise ValueError("INVALID_REQUEST_ID")

    def mutate(state: dict) -> dict:
        row = state.setdefault(PENDING_KEY, {}).get(request_id)
        if not isinstance(row, dict) or str(row.get("uid")) != uid:
            raise ValueError("DISTRIBUTION_REQUEST_NOT_FOUND")
        if row.get("status") != "prepared":
            raise ValueError("DISTRIBUTION_REQUEST_NOT_PENDING")
        row["status"] = "cancelled"
        row["cancelled_at"] = _iso(_now())
        return {"status": "cancelled", "request_id": request_id}

    return state_manager.atomic_update(mutate)


def secondary_distribution_snapshot(uid: Any) -> dict[str, Any]:
    uid = str(uid)
    db = state_manager.load_db()
    record = (db.get(REGISTRY_KEY, {}) or {}).get(uid)
    if not isinstance(record, dict) or record.get("status") != "active":
        return {"active": False}

    now = _now()
    completed = _completed_today(db, uid, now)
    pending = Decimal("0")
    rows = db.get(PENDING_KEY, {}) if isinstance(db, dict) else {}
    for row in rows.values() if isinstance(rows, dict) else []:
        if not isinstance(row, dict) or str(row.get("uid")) != uid or row.get("status") != "prepared":
            continue
        try:
            created = datetime.fromisoformat(str(row.get("prepared_at")).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if created + timedelta(seconds=REQUEST_TTL_SECONDS) < now:
            continue
        if _utc_day(created) == _utc_day(now):
            try:
                pending += _parse_amount(row.get("amount_slh"))
            except ValueError:
                continue

    limit_mode = str(record.get("limit_mode") or "bounded").strip().lower()
    if limit_mode == "bounded":
        daily_limit = _limit(record.get("daily_limit_slh"), "DAILY_LIMIT")
        per_tx = _limit(record.get("per_tx_limit_slh"), "PER_TX_LIMIT")
        daily_remaining = max(Decimal("0"), daily_limit - completed - pending)
        per_tx_value = str(per_tx)
        daily_value = str(daily_limit)
        confirmed_value = str(completed)
        pending_value = str(pending)
        remaining_value = str(daily_remaining)
    elif limit_mode == "unbounded":
        per_tx_value = "unlimited"
        daily_value = "unlimited"
        confirmed_value = str(completed)
        pending_value = str(pending)
        remaining_value = "unlimited"
    else:
        raise ValueError("INVALID_LIMIT_MODE")
    return {
        "active": True,
        "uid": uid,
        "wallet": record.get("address"),
        "role": record.get("role"),
        "mode": record.get("mode"),
        "limit_mode": limit_mode,
        "per_tx_limit_slh": per_tx_value,
        "daily_limit_slh": daily_value,
        "daily_confirmed_slh": confirmed_value,
        "daily_pending_slh": pending_value,
        "daily_remaining_slh": remaining_value,
        "timezone": "UTC",
    }
