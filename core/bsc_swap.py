"""Safe BSC swap quote and transaction preparation.

This module does not hold keys, sign, broadcast, or mutate internal balances.
It prepares a user-signed PancakeSwap V2 transaction for BNB <-> USDT.
"""
from __future__ import annotations

import time
from decimal import Decimal
from typing import Any

from eth_abi import encode

from core.bsc_execution import (
    NETWORKS,
    _bound_account,
    _checksum_address,
    _hex_quantity,
    _parse_units,
    _client,
    _network,
    execution_enabled,
    mainnet_allowed,
    network_name,
    _fee_fields,
)

V2_GET_AMOUNTS_OUT_SELECTOR = "d06ca61f"
V2_SWAP_EXACT_ETH_FOR_TOKENS_SELECTOR = "7ff36ab5"
V2_SWAP_EXACT_TOKENS_FOR_ETH_SELECTOR = "18cbafe5"
ERC20_APPROVE_SELECTOR = "095ea7b3"
ERC20_ALLOWANCE_SELECTOR = "dd62ed3e"
ERC20_BALANCE_OF_SELECTOR = "70a08231"
ERC20_DECIMALS_SELECTOR = "313ce567"

DEFAULTS = {
    "bsc-testnet": {
        "router": "0x9Ac64Cc6e4415144C455BD8E4837Fea55603e5c3",
        "wbnb": "0xae13d989daC2f0dEbFf460aC112a837C89BAa7cd",
        "usdt_env": "SLH_BSC_USDT_TESTNET_ADDRESS",
    },
    "bsc-mainnet": {
        "router": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
        "wbnb": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        "usdt_env": "SLH_BSC_USDT_MAINNET_ADDRESS",
    },
}

MAX_SLIPPAGE_BPS = 1_000
DEFAULT_DEADLINE_SECONDS = 1_200


def _decode_uint256(raw: bytes) -> int:
    return int(raw.hex(), 16)


def _cfg() -> dict[str, Any]:
    """Use the canonical execution-layer network config, including its RPC URL."""
    import os

    exec_cfg = _network()
    name = exec_cfg["name"]
    router = os.getenv("SLH_BSC_PANCAKE_V2_ROUTER", "").strip() or DEFAULTS[name]["router"]
    wbnb = os.getenv("SLH_BSC_WBNB_ADDRESS", "").strip() or DEFAULTS[name]["wbnb"]
    usdt = os.getenv(DEFAULTS[name]["usdt_env"], "").strip()

    return {
        "name": name,
        "chain_id": exec_cfg["chain_id"],
        "rpc_url": exec_cfg["rpc_url"],
        "router": _checksum_address(router, field="router"),
        "wbnb": _checksum_address(wbnb, field="token"),
        "usdt": _checksum_address(usdt, field="token") if usdt else None,
        "native_symbol": exec_cfg["native_symbol"],
    }


def policy_snapshot() -> dict[str, Any]:
    cfg = _cfg()
    return {
        "enabled": execution_enabled(),
        "network": cfg["name"],
        "chain_id": cfg["chain_id"],
        "router": cfg["router"],
        "wbnb": cfg["wbnb"],
        "usdt_configured": bool(cfg["usdt"]),
        "broadcast": False,
        "custody": False,
    }


def _require_enabled() -> dict[str, Any]:
    cfg = _cfg()
    if not execution_enabled():
        raise ValueError("BSC_EXECUTION_DISABLED")
    return cfg


def _token_decimals(web3, token: str) -> int:
    raw = web3.eth.call({"to": token, "data": "0x" + ERC20_DECIMALS_SELECTOR})
    decimals = _decode_uint256(raw)
    if not 0 <= decimals <= 36:
        raise ValueError("TOKEN_DECIMALS_INVALID")
    return decimals


def _quote_raw(web3, router: str, path: list[str], amount_in_raw: int) -> list[int]:
    if amount_in_raw <= 0:
        raise ValueError("INVALID_AMOUNT")
    data = "0x" + V2_GET_AMOUNTS_OUT_SELECTOR + encode(
        ["uint256", "address[]"],
        [amount_in_raw, path],
    ).hex()
    raw = web3.eth.call({"to": router, "data": data})
    values = list(__import__("eth_abi").decode(["uint256[]"], raw))
    amounts = [int(x) for x in values[0]]
    if len(amounts) != len(path):
        raise ValueError("INVALID_QUOTE_RESPONSE")
    return amounts


def _amount_out_min(amount_out_raw: int, slippage_bps: int) -> int:
    if amount_out_raw <= 0:
        raise ValueError("INVALID_QUOTE_AMOUNT")
    if not isinstance(slippage_bps, int) or not 0 <= slippage_bps <= MAX_SLIPPAGE_BPS:
        raise ValueError("INVALID_SLIPPAGE_BPS")
    return (amount_out_raw * (10_000 - slippage_bps)) // 10_000


def _deadline(seconds: int | None = None) -> int:
    value = DEFAULT_DEADLINE_SECONDS if seconds is None else int(seconds)
    if value < 60 or value > 3_600:
        raise ValueError("INVALID_DEADLINE_SECONDS")
    return int(time.time()) + value


def _encode_swap_exact_eth_for_tokens(
    amount_out_min: int,
    path: list[str],
    recipient: str,
    deadline: int,
) -> str:
    return "0x" + V2_SWAP_EXACT_ETH_FOR_TOKENS_SELECTOR + encode(
        ["uint256", "address[]", "address", "uint256"],
        [amount_out_min, path, recipient, deadline],
    ).hex()


def _encode_swap_exact_tokens_for_eth(
    amount_in: int,
    amount_out_min: int,
    path: list[str],
    recipient: str,
    deadline: int,
) -> str:
    return "0x" + V2_SWAP_EXACT_TOKENS_FOR_ETH_SELECTOR + encode(
        ["uint256", "uint256", "address[]", "address", "uint256"],
        [amount_in, amount_out_min, path, recipient, deadline],
    ).hex()


def _encode_approve(spender: str, amount_raw: int) -> str:
    return "0x" + ERC20_APPROVE_SELECTOR + encode(
        ["address", "uint256"],
        [spender, amount_raw],
    ).hex()


def quote_bnb_usdt(uid: str, amount_bnb: str) -> dict[str, Any]:
    cfg = _require_enabled()
    if not cfg["usdt"]:
        raise ValueError("BSC_USDT_NOT_CONFIGURED")
    web3 = _client(cfg)
    sender = _bound_account(uid)
    usdt_decimals = _token_decimals(web3, cfg["usdt"])
    amount_in_raw = _parse_units(amount_bnb, 18)
    amounts = _quote_raw(web3, cfg["router"], [cfg["wbnb"], cfg["usdt"]], amount_in_raw)
    return {
        "ok": True,
        "trade": "BNB_USDT",
        "network": cfg["name"],
        "chain_id": cfg["chain_id"],
        "router": cfg["router"],
        "from": sender,
        "token_in": cfg["wbnb"],
        "token_out": cfg["usdt"],
        "token_out_decimals": usdt_decimals,
        "amount_in_raw": amount_in_raw,
        "amount_in": str(Decimal(amount_in_raw) / Decimal(10**18)),
        "amount_out_raw": amounts[-1],
        "amount_out": str(Decimal(amounts[-1]) / Decimal(10**usdt_decimals)),
        "path": [cfg["wbnb"], cfg["usdt"]],
        "block_number": int(web3.eth.block_number),
        "quoted_at": int(time.time()),
        "broadcast": False,
    }


def quote_usdt_bnb(uid: str, amount_usdt: str) -> dict[str, Any]:
    cfg = _require_enabled()
    if not cfg["usdt"]:
        raise ValueError("BSC_USDT_NOT_CONFIGURED")
    web3 = _client(cfg)
    sender = _bound_account(uid)
    usdt_decimals = _token_decimals(web3, cfg["usdt"])
    amount_in_raw = _parse_units(amount_usdt, usdt_decimals)
    amounts = _quote_raw(web3, cfg["router"], [cfg["usdt"], cfg["wbnb"]], amount_in_raw)
    return {
        "ok": True,
        "trade": "USDT_BNB",
        "network": cfg["name"],
        "chain_id": cfg["chain_id"],
        "router": cfg["router"],
        "from": sender,
        "token_in": cfg["usdt"],
        "token_out": cfg["wbnb"],
        "token_out_decimals": 18,
        "amount_in_raw": amount_in_raw,
        "amount_in": str(Decimal(amount_in_raw) / Decimal(10**usdt_decimals)),
        "amount_out_raw": amounts[-1],
        "amount_out": str(Decimal(amounts[-1]) / Decimal(10**18)),
        "path": [cfg["usdt"], cfg["wbnb"]],
        "block_number": int(web3.eth.block_number),
        "quoted_at": int(time.time()),
        "broadcast": False,
    }


def prepare_bnb_to_usdt(
    uid: str,
    amount_bnb: str,
    slippage_bps: int,
    *,
    deadline_seconds: int = DEFAULT_DEADLINE_SECONDS,
) -> dict[str, Any]:
    cfg = _require_enabled()
    if not cfg["usdt"]:
        raise ValueError("BSC_USDT_NOT_CONFIGURED")
    web3 = _client(cfg)
    sender = _bound_account(uid)
    amount_in_raw = _parse_units(amount_bnb, 18)
    amounts = _quote_raw(web3, cfg["router"], [cfg["wbnb"], cfg["usdt"]], amount_in_raw)
    amount_out_raw = amounts[-1]
    amount_out_min = _amount_out_min(amount_out_raw, slippage_bps)
    deadline = _deadline(deadline_seconds)
    native_balance = int(web3.eth.get_balance(sender))
    if native_balance < amount_in_raw:
        raise ValueError("INSUFFICIENT_NATIVE_GAS")
    gas = int(web3.eth.estimate_gas({
        "from": sender,
        "to": cfg["router"],
        "value": hex(amount_in_raw),
        "data": _encode_swap_exact_eth_for_tokens(
            amount_out_min, [cfg["wbnb"], cfg["usdt"]], sender, deadline
        ),
    }))
    fees = _fee_fields(web3)
    max_fee = int(fees["maxFeePerGas"], 16)
    required_native = amount_in_raw + gas * max_fee
    if native_balance < required_native:
        raise ValueError("INSUFFICIENT_BNB_FOR_SWAP_AND_GAS")
    return {
        "ok": True,
        "trade": "BNB_USDT",
        "network": cfg["name"],
        "chain_id": cfg["chain_id"],
        "router": cfg["router"],
        "from": sender,
        "recipient": sender,
        "amount_in_raw": amount_in_raw,
        "amount_in": str(Decimal(amount_in_raw) / Decimal(10**18)),
        "quoted_out_raw": amount_out_raw,
        "minimum_out_raw": amount_out_min,
        "slippage_bps": slippage_bps,
        "deadline": deadline,
        "nonce": int(web3.eth.get_transaction_count(sender, "pending")),
        "tx": {
            "from": sender,
            "to": cfg["router"],
            "value": _hex_quantity(amount_in_raw),
            "data": _encode_swap_exact_eth_for_tokens(
                amount_out_min, [cfg["wbnb"], cfg["usdt"]], sender, deadline
            ),
            "gas": _hex_quantity(gas),
            "gas_limit": _hex_quantity(gas),
            "nonce": _hex_quantity(int(web3.eth.get_transaction_count(sender, "pending"))),
            "chainId": _hex_quantity(cfg["chain_id"]),
            **fees,
        },
        "estimated_fee_raw": gas * max_fee,
        "broadcast": False,
        "approval_required": False,
    }


def prepare_usdt_to_bnb(
    uid: str,
    amount_usdt: str,
    slippage_bps: int,
    *,
    deadline_seconds: int = DEFAULT_DEADLINE_SECONDS,
) -> dict[str, Any]:
    cfg = _require_enabled()
    if not cfg["usdt"]:
        raise ValueError("BSC_USDT_NOT_CONFIGURED")
    web3 = _client(cfg)
    sender = _bound_account(uid)
    usdt_decimals = _token_decimals(web3, cfg["usdt"])
    amount_in_raw = _parse_units(amount_usdt, usdt_decimals)
    amounts = _quote_raw(web3, cfg["router"], [cfg["usdt"], cfg["wbnb"]], amount_in_raw)
    amount_out_raw = amounts[-1]
    amount_out_min = _amount_out_min(amount_out_raw, slippage_bps)
    deadline = _deadline(deadline_seconds)
    allowance = _decode_uint256(web3.eth.call({
        "to": cfg["usdt"],
        "data": "0x" + ERC20_ALLOWANCE_SELECTOR + encode(
            ["address", "address"],
            [sender, cfg["router"]],
        ).hex(),
    }))
    approval = None
    if allowance < amount_in_raw:
        approval_data = _encode_approve(cfg["router"], amount_in_raw)
        approval_gas = int(web3.eth.estimate_gas({
            "from": sender,
            "to": cfg["usdt"],
            "value": 0,
            "data": approval_data,
        }))
        approval = {
            "from": sender,
            "to": cfg["usdt"],
            "value": "0x0",
            "data": approval_data,
            "gas": _hex_quantity(approval_gas),
            "gasPrice": _hex_quantity(int(web3.eth.gas_price)),
        }
    token_balance = _decode_uint256(web3.eth.call({
        "to": cfg["usdt"],
        "data": "0x" + ERC20_BALANCE_OF_SELECTOR + sender[2:].lower().zfill(64),
    }))
    if token_balance < amount_in_raw:
        raise ValueError("INSUFFICIENT_USDT_BALANCE")
    gas_data = _encode_swap_exact_tokens_for_eth(
        amount_in_raw, amount_out_min, [cfg["usdt"], cfg["wbnb"]], sender, deadline
    )
    swap_gas = int(web3.eth.estimate_gas({
        "from": sender,
        "to": cfg["router"],
        "value": 0,
        "data": gas_data,
    }))
    gas_price = int(web3.eth.gas_price)
    native_balance = int(web3.eth.get_balance(sender))
    total_gas = swap_gas + (int(approval["gas"], 16) if approval else 0)
    if native_balance < total_gas * gas_price:
        raise ValueError("INSUFFICIENT_BNB_FOR_GAS")
    return {
        "ok": True,
        "trade": "USDT_BNB",
        "network": cfg["name"],
        "chain_id": cfg["chain_id"],
        "router": cfg["router"],
        "from": sender,
        "recipient": sender,
        "amount_in_raw": amount_in_raw,
        "amount_in": str(Decimal(amount_in_raw) / Decimal(10**usdt_decimals)),
        "quoted_out_raw": amount_out_raw,
        "minimum_out_raw": amount_out_min,
        "slippage_bps": slippage_bps,
        "deadline": deadline,
        "approval": approval,
        "tx": {
            "from": sender,
            "to": cfg["router"],
            "value": "0x0",
            "data": gas_data,
            "gas": _hex_quantity(swap_gas),
            "gasPrice": _hex_quantity(gas_price),
        },
        "estimated_fee_raw": swap_gas * gas_price,
        "broadcast": False,
        "approval_required": approval is not None,
    }
