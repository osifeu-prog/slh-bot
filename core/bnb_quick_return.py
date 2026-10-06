"""Owner-only native BNB Quick Return preset and read-only verifier.

The browser signs and broadcasts. The server only resolves verified wallet
bindings and verifies the resulting native BNB transaction on BSC.
"""

from __future__ import annotations

from typing import Any

from web3 import Web3

from core.distribution_wallet_registry import _bsc_config
from core.identity import OWNER_TELEGRAM_ID
from core.wallet_binding import get_binding

BNB_RETURN_AMOUNT = "0.01"
BNB_RETURN_WEI = 10**16
RECIPIENT_UID = "5010371391"
REQUIRED_CONFIRMATIONS = 15


def get_bnb_return_config(uid: Any) -> dict[str, Any]:
    uid = str(uid or "").strip()
    if uid != str(OWNER_TELEGRAM_ID):
        raise PermissionError("OWNER_ONLY")

    sender_binding = get_binding(uid)
    recipient_binding = get_binding(RECIPIENT_UID)
    if not sender_binding:
        raise ValueError("OWNER_BSC_WALLET_NOT_VERIFIED")
    if not recipient_binding:
        raise ValueError("RECIPIENT_BSC_WALLET_NOT_VERIFIED")

    sender = str(sender_binding.get("address") or "").strip()
    recipient = str(recipient_binding.get("address") or "").strip()
    if not Web3.is_address(sender):
        raise ValueError("OWNER_BSC_WALLET_NOT_VERIFIED")
    if not Web3.is_address(recipient):
        raise ValueError("RECIPIENT_BSC_WALLET_NOT_VERIFIED")
    sender = Web3.to_checksum_address(sender)
    recipient = Web3.to_checksum_address(recipient)
    if sender.lower() == recipient.lower():
        raise ValueError("BNB_RETURN_SELF_TRANSFER_BLOCKED")

    bsc = _bsc_config()
    rpc = str(bsc.get("rpc") or "").strip()
    if not rpc:
        raise ValueError("BSC_RPC_NOT_CONFIGURED")
    if int(bsc.get("chain_id") or 0) != 56:
        raise ValueError("BSC_CHAIN_ID_MISMATCH")

    return {
        "ok": True,
        "purpose": "BNB_RETURN_SMOKE",
        "label": "צביקה",
        "sender_uid": uid,
        "sender": sender,
        "recipient_uid": RECIPIENT_UID,
        "recipient": recipient,
        "amount_bnb": BNB_RETURN_AMOUNT,
        "amount_wei": str(BNB_RETURN_WEI),
        "chain_id": 56,
        "native_symbol": "BNB",
        "required_confirmations": REQUIRED_CONFIRMATIONS,
        "signing": "user_wallet_only",
        "server_broadcast": False,
        "custody": False,
    }


def verify_bnb_return(uid: Any, tx_hash: Any) -> dict[str, Any]:
    config = get_bnb_return_config(uid)
    raw_hash = str(tx_hash or "").strip()
    if not raw_hash:
        raise ValueError("INVALID_TX_HASH")

    w3 = Web3(Web3.HTTPProvider(str(_bsc_config()["rpc"]), request_kwargs={"timeout": 8}))
    if not w3.is_connected():
        raise ValueError("BSC_RPC_UNAVAILABLE")
    if int(w3.eth.chain_id) != 56:
        raise ValueError("BSC_CHAIN_ID_MISMATCH")

    try:
        receipt = w3.eth.get_transaction_receipt(raw_hash)
        tx = w3.eth.get_transaction(raw_hash)
    except Exception as exc:
        if type(exc).__name__ == "TransactionNotFound":
            return {
                "ok": False,
                "error": "TRANSACTION_NOT_FOUND_RETRYABLE",
                "retryable": True,
                "tx_hash": raw_hash,
            }
        raise

    if int(receipt.get("status", 0)) != 1:
        raise ValueError("TRANSACTION_FAILED")

    tx_from = str(tx.get("from") or "")
    tx_to = str(tx.get("to") or "")
    value = int(tx.get("value", 0) or 0)
    if tx_from.lower() != config["sender"].lower():
        raise ValueError("TRANSACTION_SENDER_MISMATCH")
    if tx_to.lower() != config["recipient"].lower():
        raise ValueError("TRANSACTION_RECIPIENT_MISMATCH")
    if value != BNB_RETURN_WEI:
        raise ValueError("TRANSACTION_AMOUNT_MISMATCH")

    block_number = int(receipt["blockNumber"])
    latest_block = int(w3.eth.block_number)
    confirmations = max(0, latest_block - block_number + 1)
    if confirmations < REQUIRED_CONFIRMATIONS:
        return {
            "ok": False,
            "error": "INSUFFICIENT_CONFIRMATIONS",
            "retryable": True,
            "tx_hash": raw_hash,
            "confirmations": confirmations,
            "required_confirmations": REQUIRED_CONFIRMATIONS,
        }

    return {
        "ok": True,
        "status": "verified",
        "purpose": "BNB_RETURN_SMOKE",
        "tx_hash": raw_hash,
        "chain_id": 56,
        "sender": config["sender"],
        "recipient": config["recipient"],
        "amount_bnb": BNB_RETURN_AMOUNT,
        "amount_wei": str(BNB_RETURN_WEI),
        "block": block_number,
        "confirmations": confirmations,
        "required_confirmations": REQUIRED_CONFIRMATIONS,
        "server_broadcast": False,
        "custody": False,
    }
