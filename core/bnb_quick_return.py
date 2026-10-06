"""Owner-only native BNB return presets and read-only verifier.

The browser signs and broadcasts. The server only resolves verified wallet
bindings and verifies the resulting native BNB transaction on BSC.

Each verified transaction also reports its actual network fee so the UI can
show a transparent gross amount + gas cost statement.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from web3 import Web3

from core.distribution_wallet_registry import _bsc_config
from core.identity import OWNER_TELEGRAM_ID
from core.wallet_binding import get_binding

RECIPIENT_UID = "5010371391"
REQUIRED_CONFIRMATIONS = 15

BNB_RETURN_PRESETS = {
    "smoke": {
        "purpose": "BNB_RETURN_SMOKE",
        "label": "צביקה · Smoke",
        "amount_bnb": Decimal("0.01"),
    },
    "repay_1": {
        "purpose": "BNB_REPAYMENT",
        "label": "צביקה · החזר 1 BNB",
        "amount_bnb": Decimal("1"),
    },
}


def _preset(preset: Any) -> dict[str, Any]:
    name = str(preset or "smoke").strip().lower()
    if name not in BNB_RETURN_PRESETS:
        raise ValueError("BNB_RETURN_PRESET_UNKNOWN")
    return BNB_RETURN_PRESETS[name]


def get_bnb_return_config(uid: Any, preset: Any = "smoke") -> dict[str, Any]:
    uid = str(uid or "").strip()
    if uid != str(OWNER_TELEGRAM_ID):
        raise PermissionError("OWNER_ONLY")

    selected = _preset(preset)
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

    amount_wei = int(selected["amount_bnb"] * Decimal(10**18))

    return {
        "ok": True,
        "preset": str(preset or "smoke"),
        "purpose": selected["purpose"],
        "label": selected["label"],
        "sender_uid": uid,
        "sender": sender,
        "recipient_uid": RECIPIENT_UID,
        "recipient": recipient,
        "amount_bnb": format(selected["amount_bnb"], "f"),
        "amount_wei": str(amount_wei),
        "chain_id": 56,
        "native_symbol": "BNB",
        "required_confirmations": REQUIRED_CONFIRMATIONS,
        "signing": "user_wallet_only",
        "server_broadcast": False,
        "custody": False,
        "service_fee_bnb": "0",
        "service_fee_policy": "not_included_in_transfer",
    }


def verify_bnb_return(
    uid: Any,
    tx_hash: Any,
    preset: Any = "smoke",
) -> dict[str, Any]:
    config = get_bnb_return_config(uid, preset=preset)
    raw_hash = str(tx_hash or "").strip()
    if not raw_hash:
        raise ValueError("INVALID_TX_HASH")

    w3 = Web3(
        Web3.HTTPProvider(
            str(_bsc_config()["rpc"]),
            request_kwargs={"timeout": 8},
        )
    )
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
    expected_value = int(config["amount_wei"])
    if tx_from.lower() != config["sender"].lower():
        raise ValueError("TRANSACTION_SENDER_MISMATCH")
    if tx_to.lower() != config["recipient"].lower():
        raise ValueError("TRANSACTION_RECIPIENT_MISMATCH")
    if value != expected_value:
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

    gas_used = int(receipt.get("gasUsed", 0) or 0)
    effective_gas_price = receipt.get("effectiveGasPrice")
    if effective_gas_price is None:
        effective_gas_price = tx.get("gasPrice", 0)
    gas_price_wei = int(effective_gas_price or 0)
    gas_fee_wei = gas_used * gas_price_wei
    total_debit_wei = value + gas_fee_wei

    return {
        "ok": True,
        "status": "verified",
        "purpose": config["purpose"],
        "preset": config["preset"],
        "tx_hash": raw_hash,
        "chain_id": 56,
        "sender": config["sender"],
        "recipient": config["recipient"],
        "amount_bnb": config["amount_bnb"],
        "amount_wei": str(expected_value),
        "block": block_number,
        "confirmations": confirmations,
        "required_confirmations": REQUIRED_CONFIRMATIONS,
        "gas_used": str(gas_used),
        "gas_price_wei": str(gas_price_wei),
        "gas_fee_wei": str(gas_fee_wei),
        "gas_fee_bnb": format(Decimal(gas_fee_wei) / Decimal(10**18), "f"),
        "service_fee_bnb": config["service_fee_bnb"],
        "service_fee_policy": config["service_fee_policy"],
        "recipient_receives_bnb": config["amount_bnb"],
        "sender_total_debit_bnb": format(
            Decimal(total_debit_wei) / Decimal(10**18),
            "f",
        ),
        "server_broadcast": False,
        "custody": False,
    }
