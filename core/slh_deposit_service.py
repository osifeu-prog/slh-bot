"""Canonical SLH BEP-20 deposit settlement.

A deposit becomes a live internal SLH balance only after:
1. Telegram -> BNB wallet ownership binding is verified.
2. The BSC transaction succeeded and has the required confirmations.
3. The configured SLH contract emitted a Transfer from the bound wallet to the
   configured Treasury.

No token minting, burning, or synthetic balance creation occurs here.
"""
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import json
from pathlib import Path

from web3 import Web3

import state_manager
from core.binance_connector import get_bsc_config
from core.wallet_binding import get_binding


TRANSFER_TOPIC = Web3.keccak(text="Transfer(address,address,uint256)").hex()
LIVE_TOKEN_FIELD = "live_token_balance"
TOKEN_LEDGER_KEY = "slh_token_ledger"
CLAIMED_KEY = "claimed_slh_deposits"


def _config():
    cfg = get_bsc_config()
    try:
        db = json.loads(Path("state/db.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        db = {}
    return {**cfg, **db.get("bsc_settings", {})}


def _address_from_topic(topic):
    raw = topic.hex() if hasattr(topic, "hex") else str(topic)
    raw = raw[2:] if raw.startswith("0x") else raw
    if len(raw) < 40:
        raise ValueError("INVALID_TRANSFER_TOPIC")
    return Web3.to_checksum_address("0x" + raw[-40:])


def verify_slh_deposit(tx_hash):
    cfg = _config()
    if not cfg.get("rpc"):
        return {"ok": False, "error": "BSC_RPC_NOT_CONFIGURED"}
    if not cfg.get("treasury_wallet"):
        return {"ok": False, "error": "BNB_TREASURY_NOT_CONFIGURED"}
    if not cfg.get("token_contract"):
        return {"ok": False, "error": "SLH_TOKEN_NOT_CONFIGURED"}

    w3 = Web3(Web3.HTTPProvider(cfg["rpc"]))
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    if not receipt or receipt.get("status") != 1:
        return {
            "ok": False,
            "error": "BSC_TX_FAILED",
            "status": receipt.get("status") if receipt else None,
        }

    block = int(receipt.get("blockNumber", 0))
    latest_block = int(w3.eth.block_number)
    confirmations = max(0, latest_block - block + 1)
    required = int(cfg.get("confirmations") or 15)
    if confirmations < required:
        return {
            "ok": False,
            "error": "INSUFFICIENT_CONFIRMATIONS",
            "confirmations": confirmations,
            "required_confirmations": required,
            "block": block,
            "tx_hash": tx_hash,
        }

    token_contract = Web3.to_checksum_address(cfg["token_contract"])
    treasury = Web3.to_checksum_address(cfg["treasury_wallet"])
    matches = []
    for log in receipt.get("logs", []):
        try:
            if Web3.to_checksum_address(log["address"]) != token_contract:
                continue
            topics = log.get("topics") or []
            if len(topics) != 3:
                continue
            topic0 = topics[0].hex() if hasattr(topics[0], "hex") else str(topics[0])
            if topic0.lower() != TRANSFER_TOPIC.lower():
                continue
            sender = _address_from_topic(topics[1])
            recipient = _address_from_topic(topics[2])
            if recipient.lower() != treasury.lower():
                continue
            data_value = log.get("data", "0x0")
            raw_value = int(data_value.hex(), 16) if hasattr(data_value, "hex") else int(str(data_value), 16)
            matches.append({
                "from": sender,
                "to": recipient,
                "raw_amount": raw_value,
                "log_index": int(log.get("logIndex", 0)),
            })
        except (KeyError, ValueError, TypeError):
            continue

    if not matches:
        return {
            "ok": False,
            "error": "SLH_TRANSFER_NOT_FOUND",
            "token_contract": token_contract,
            "treasury_wallet": treasury,
            "tx_hash": tx_hash,
        }

    if len(matches) != 1:
        return {
            "ok": False,
            "error": "AMBIGUOUS_SLH_TRANSFER",
            "matches": len(matches),
            "tx_hash": tx_hash,
        }

    match = matches[0]

    try:
        token = w3.eth.contract(
            address=token_contract,
            abi=[{
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function",
            }],
        )
        decimals = int(token.functions.decimals().call())
    except Exception as exc:
        return {"ok": False, "error": "SLH_DECIMALS_UNAVAILABLE"}

    amount = Decimal(match["raw_amount"]) / (Decimal(10) ** decimals)
    if not amount.is_finite() or amount <= 0:
        return {"ok": False, "error": "INVALID_SLH_AMOUNT"}

    return {
        "ok": True,
        "tx_hash": tx_hash,
        "from": match["from"],
        "to": match["to"],
        "amount_slh": float(amount),
        "raw_amount": match["raw_amount"],
        "decimals": decimals,
        "block": block,
        "confirmations": confirmations,
        "required_confirmations": required,
        "token_contract": token_contract,
        "treasury_wallet": treasury,
    }


def settle_slh_deposit(uid, tx_hash):
    uid = str(uid)
    tx_hash = str(tx_hash or "").strip()
    if not tx_hash:
        raise ValueError("INVALID_TX_HASH")

    binding = get_binding(uid)
    if not binding:
        raise ValueError("BNB_WALLET_NOT_VERIFIED")

    verified = verify_slh_deposit(tx_hash)
    if not verified.get("ok"):
        raise ValueError(verified.get("error", "SLH_TX_NOT_VERIFIED"))

    sender = str(verified.get("from", ""))
    bound = str(binding.get("address", ""))
    if not sender or sender.lower() != bound.lower():
        raise ValueError("SLH_TX_SENDER_NOT_BOUND_WALLET")

    amount = Decimal(str(verified.get("amount_slh", 0)))
    if not amount.is_finite() or amount <= 0:
        raise ValueError("INVALID_SLH_AMOUNT")

    def mutate(db):
        users = db.setdefault("users", {})
        user = users.get(uid)
        if not isinstance(user, dict):
            raise ValueError("USER_NOT_FOUND")
        claimed = db.setdefault(CLAIMED_KEY, {})
        existing = claimed.get(tx_hash.lower())
        if existing is not None:
            wallet = user.setdefault("wallet", {})
            return {
                "status": "duplicate",
                "uid": uid,
                "tx_hash": tx_hash,
                "amount_slh": existing.get("amount_slh", 0),
                "live_token_balance": wallet.get(LIVE_TOKEN_FIELD, 0),
                "token_balance": wallet.get("token_balance", 0),
            }

        wallet = user.setdefault("wallet", {})
        before_total = Decimal(str(wallet.get("token_balance", 0) or 0))
        before_live = Decimal(str(wallet.get(LIVE_TOKEN_FIELD, 0) or 0))
        after_total = before_total + amount
        after_live = before_live + amount

        wallet["token_balance"] = float(after_total)
        wallet[LIVE_TOKEN_FIELD] = float(after_live)

        now = datetime.now(timezone.utc).isoformat()
        claimed[tx_hash.lower()] = {
            "uid": uid,
            "amount_slh": float(amount),
            "tx_hash": tx_hash,
            "token_contract": verified["token_contract"],
            "treasury_wallet": verified["treasury_wallet"],
            "block": verified["block"],
            "claimed_at": now,
        }

        db.setdefault(TOKEN_LEDGER_KEY, []).append({
            "event_id": f"onchain:slh:{tx_hash.lower()}",
            "from_uid": sender.lower(),
            "to_uid": uid,
            "amount": float(amount),
            "reason": "onchain:deposit:slh",
            "kind": "onchain_deposit",
            "tx_hash": tx_hash,
            "token_contract": verified["token_contract"],
            "treasury_wallet": verified["treasury_wallet"],
            "before": float(before_live),
            "after": float(after_live),
            "timestamp": now,
        })

        return {
            "status": "applied",
            "uid": uid,
            "tx_hash": tx_hash,
            "amount_slh": float(amount),
            "live_token_balance": float(after_live),
            "token_balance": float(after_total),
            "block": verified["block"],
            "confirmations": verified["confirmations"],
        }

    return state_manager.atomic_update(mutate)
