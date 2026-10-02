"""Safe BSC execution preparation for user-signed transactions.

This module NEVER stores keys and NEVER broadcasts transactions.
It prepares deterministic native BNB and ERC-20 transfer payloads after:
1. explicit execution feature gate,
2. explicit BSC network selection,
3. verified Telegram -> BNB wallet binding,
4. strict address / amount validation,
5. read-only RPC checks.

Swap execution is intentionally outside this phase.
"""
from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from typing import Any

from web3 import Web3
from eth_account import Account

DEFAULT_TESTNET_RPC = "https://bsc-testnet-dataseed.bnbchain.org"
DEFAULT_MAINNET_RPC = "https://bsc-dataseed.bnbchain.org"

NETWORKS = {
    "bsc-testnet": {
        "chain_id": 97,
        "rpc_env": "SLH_BSC_TESTNET_RPC_URL",
        "rpc_default": DEFAULT_TESTNET_RPC,
        "native_symbol": "tBNB",
        "usdt_env": "SLH_BSC_USDT_TESTNET_ADDRESS",
    },
    "bsc-mainnet": {
        "chain_id": 56,
        "rpc_env": "SLH_BSC_MAINNET_RPC_URL",
        "rpc_default": DEFAULT_MAINNET_RPC,
        "native_symbol": "BNB",
        "usdt_env": "SLH_BSC_USDT_MAINNET_ADDRESS",
    },
}

ERC20_TRANSFER_SELECTOR = "a9059cbb"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
NATIVE_DECIMALS = 18


def execution_enabled() -> bool:
    return os.getenv("SLH_BSC_EXECUTION_ENABLED", "0").strip() == "1"


def network_name() -> str:
    value = os.getenv("SLH_BSC_EXECUTION_NETWORK", "bsc-testnet").strip().lower()
    return value if value in NETWORKS else "bsc-testnet"


def mainnet_allowed() -> bool:
    return os.getenv("SLH_BSC_EXECUTION_ALLOW_MAINNET", "0").strip() == "1"


def _network() -> dict[str, Any]:
    name = network_name()
    cfg = NETWORKS[name]
    rpc = os.getenv(cfg["rpc_env"], "").strip() or cfg["rpc_default"]
    usdt = os.getenv(cfg["usdt_env"], "").strip()
    if name == "bsc-mainnet" and not mainnet_allowed():
        raise ValueError("BSC_MAINNET_EXECUTION_DISABLED")
    return {
        "name": name,
        "chain_id": cfg["chain_id"],
        "rpc_url": rpc,
        "native_symbol": cfg["native_symbol"],
        "usdt_address": usdt or None,
    }


def policy_snapshot() -> dict[str, Any]:
    cfg = _network()
    return {
        "enabled": execution_enabled(),
        "network": cfg["name"],
        "chain_id": cfg["chain_id"],
        "native_symbol": cfg["native_symbol"],
        "usdt_configured": bool(cfg["usdt_address"]),
        "mainnet_allowed": mainnet_allowed(),
        "broadcast": False,
        "custody": False,
    }


def _require_enabled() -> dict[str, Any]:
    cfg = _network()
    if not execution_enabled():
        raise ValueError("BSC_EXECUTION_DISABLED")
    return cfg


def _checksum_address(value: str, *, field: str) -> str:
    raw = str(value or "").strip()
    if not raw or not Web3.is_address(raw):
        raise ValueError(f"INVALID_{field.upper()}_ADDRESS")
    address = Web3.to_checksum_address(raw)
    if address == ZERO_ADDRESS:
        raise ValueError(f"INVALID_{field.upper()}_ADDRESS")
    return address


def _parse_units(value: str, decimals: int) -> int:
    text = str(value or "").strip()
    if not text:
        raise ValueError("INVALID_AMOUNT")
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("INVALID_AMOUNT") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("INVALID_AMOUNT")
    if amount.as_tuple().exponent < -decimals:
        raise ValueError("TOO_MANY_DECIMALS")
    raw = int(amount * (Decimal(10) ** decimals))
    if raw <= 0:
        raise ValueError("INVALID_AMOUNT")
    return raw


def _hex_quantity(value: int) -> str:
    if int(value) < 0:
        raise ValueError("INVALID_QUANTITY")
    return hex(int(value))


def _encode_erc20_transfer(recipient: str, amount_raw: int) -> str:
    recipient_bytes = recipient[2:].lower().zfill(64)
    amount_bytes = hex(amount_raw)[2:].zfill(64)
    return "0x" + ERC20_TRANSFER_SELECTOR + recipient_bytes + amount_bytes


def _client(cfg: dict[str, Any]) -> Web3:
    web3 = Web3(Web3.HTTPProvider(cfg["rpc_url"], request_kwargs={"timeout": 8}))
    if not web3.is_connected():
        raise ValueError("BSC_RPC_UNAVAILABLE")
    actual = int(web3.eth.chain_id)
    if actual != cfg["chain_id"]:
        raise ValueError("BSC_RPC_CHAIN_MISMATCH")
    return web3


def _bound_account(uid: str) -> str:
    from core.wallet_binding import get_binding

    binding = get_binding(str(uid))
    if not binding:
        raise ValueError("BNB_WALLET_NOT_VERIFIED")
    return _checksum_address(binding.get("address"), field="sender")


def _normalize_raw_transaction(raw_transaction: str | bytes) -> bytes:
    if isinstance(raw_transaction, bytes):
        raw = raw_transaction
    elif isinstance(raw_transaction, str):
        value = raw_transaction.strip()
        if value.startswith("0x"):
            value = value[2:]
        if not value or len(value) % 2:
            raise ValueError("INVALID_RAW_TRANSACTION")
        try:
            raw = bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError("INVALID_RAW_TRANSACTION") from exc
    else:
        raise ValueError("INVALID_RAW_TRANSACTION")
    if not raw or len(raw) > 128_000:
        raise ValueError("INVALID_RAW_TRANSACTION")
    return raw


def broadcast_signed_transaction(uid: str, raw_transaction: str | bytes) -> dict[str, Any]:
    """Broadcast a transaction already signed by the user's bound wallet.

    This function never receives or stores a private key. The signer is
    recovered from the raw transaction and must equal the verified BNB wallet
    bound to the Telegram UID. The BSC node performs the final chain/signature
    validation when the raw transaction is submitted.
    """
    cfg = _require_enabled()
    web3 = _client(cfg)
    sender = _bound_account(uid)
    raw = _normalize_raw_transaction(raw_transaction)

    try:
        recovered = Account.recover_transaction(raw)
    except Exception as exc:
        raise ValueError("INVALID_SIGNED_TRANSACTION") from exc

    recovered = _checksum_address(recovered, field="sender")
    if recovered != sender:
        raise ValueError("SIGNED_TX_SENDER_NOT_BOUND_WALLET")

    try:
        tx_hash = web3.eth.send_raw_transaction(raw)
    except Exception as exc:
        raise ValueError(f"BSC_BROADCAST_REJECTED:{type(exc).__name__}") from exc

    return {
        "ok": True,
        "network": cfg["name"],
        "chain_id": cfg["chain_id"],
        "from": sender,
        "tx_hash": tx_hash.hex(),
        "broadcast": True,
        "custody": False,
    }


def prepare_native_transfer(uid: str, recipient: str, amount: str) -> dict[str, Any]:
    cfg = _require_enabled()
    web3 = _client(cfg)
    sender = _bound_account(uid)
    destination = _checksum_address(recipient, field="recipient")
    if destination == sender:
        raise ValueError("RECIPIENT_EQUALS_SENDER")

    raw_amount = _parse_units(amount, NATIVE_DECIMALS)
    tx_value = _hex_quantity(raw_amount)
    gas = int(web3.eth.estimate_gas({"from": sender, "to": destination, "value": tx_value}))
    gas_price = int(web3.eth.gas_price)
    balance = int(web3.eth.get_balance(sender))
    required = raw_amount + (gas * gas_price)
    if balance < required:
        raise ValueError("INSUFFICIENT_BNB_FOR_VALUE_AND_GAS")

    return {
        "ok": True,
        "asset": cfg["native_symbol"],
        "asset_type": "native",
        "network": cfg["name"],
        "chain_id": cfg["chain_id"],
        "from": sender,
        "to": destination,
        "amount_raw": raw_amount,
        "amount": str(Decimal(raw_amount) / (Decimal(10) ** NATIVE_DECIMALS)),
        "tx": {
            "from": sender,
            "to": destination,
            "value": tx_value,
            "gas": _hex_quantity(gas),
            "gasPrice": _hex_quantity(gas_price),
        },
        "estimated_fee_raw": gas * gas_price,
        "balance_raw": balance,
        "broadcast": False,
    }


def prepare_erc20_transfer(
    uid: str,
    token_address: str,
    recipient: str,
    amount: str,
    *,
    asset: str = "ERC20",
) -> dict[str, Any]:
    cfg = _require_enabled()
    web3 = _client(cfg)
    sender = _bound_account(uid)
    token = _checksum_address(token_address, field="token")
    destination = _checksum_address(recipient, field="recipient")
    if destination == sender:
        raise ValueError("RECIPIENT_EQUALS_SENDER")

    decimals = int(
        web3.eth.call(
            {
                "to": token,
                "data": "0x313ce567",
            }
        ).hex(),
        16,
    )
    if decimals < 0 or decimals > 36:
        raise ValueError("TOKEN_DECIMALS_INVALID")

    raw_amount = _parse_units(amount, decimals)
    balance_raw = int(
        web3.eth.call(
            {
                "to": token,
                "data": "0x70a08231" + sender[2:].lower().zfill(64),
            }
        ).hex(),
        16,
    )
    if raw_amount > balance_raw:
        raise ValueError("INSUFFICIENT_TOKEN_BALANCE")

    data = _encode_erc20_transfer(destination, raw_amount)
    gas = int(web3.eth.estimate_gas({"from": sender, "to": token, "data": data, "value": 0}))
    gas_price = int(web3.eth.gas_price)
    native_balance = int(web3.eth.get_balance(sender))
    required_native = gas * gas_price
    if native_balance < required_native:
        raise ValueError("INSUFFICIENT_BNB_FOR_GAS")

    return {
        "ok": True,
        "asset": str(asset),
        "asset_type": "erc20",
        "token": token,
        "network": cfg["name"],
        "chain_id": cfg["chain_id"],
        "from": sender,
        "to": destination,
        "decimals": decimals,
        "amount_raw": raw_amount,
        "amount": str(Decimal(raw_amount) / (Decimal(10) ** decimals)),
        "tx": {
            "from": sender,
            "to": token,
            "value": "0x0",
            "data": data,
            "gas": _hex_quantity(gas),
            "gasPrice": _hex_quantity(gas_price),
        },
        "estimated_fee_raw": gas * gas_price,
        "native_balance_raw": native_balance,
        "token_balance_raw": balance_raw,
        "broadcast": False,
    }


def prepare_usdt_transfer(uid: str, recipient: str, amount: str) -> dict[str, Any]:
    cfg = _require_enabled()
    token = cfg.get("usdt_address")
    if not token:
        raise ValueError("BSC_USDT_NOT_CONFIGURED")
    return prepare_erc20_transfer(
        uid,
        token,
        recipient,
        amount,
        asset="USDT",
    )
