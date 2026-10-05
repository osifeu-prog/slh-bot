"""Live, non-custodial BSC swap preparation.

The server never stores keys or signs transactions. It reads live BSC state,
builds a user-signable PancakeSwap V2 transaction, and returns it to the Mini
App. Mainnet is fail-closed behind the existing BSC execution policy.
"""

from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from typing import Any

from eth_abi import encode
from web3 import Web3

from core.bsc_execution import (
    BSCExecutionError,
    NETWORKS,
    _checksum_address,
    _client,
    _fee_fields,
    _hex_quantity,
    _network,
    _bound_account,
)

ROUTER_V2 = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
BINANCE_PEG_USDC = "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d"
SLH = "0xACb0A09414CEA1C879c67bB7A877E4e19480f022"

GET_AMOUNTS_OUT = "d06ca61f"
SWAP_EXACT_ETH_FOR_TOKENS = "7ff36ab5"
SWAP_EXACT_TOKENS_FOR_ETH = "18cbafe5"
SWAP_EXACT_TOKENS_FOR_TOKENS = "38ed1739"
APPROVE = "095ea7b3"
ALLOWANCE = "dd62ed3e"
BALANCE_OF = "70a08231"
DECIMALS = "313ce567"

MAX_SLIPPAGE_BPS = 1_000


def _cfg() -> dict[str, Any]:
    cfg = _network()
    router = os.getenv("SLH_BSC_PANCAKE_V2_ROUTER", "").strip() or ROUTER_V2
    usdc = os.getenv("SLH_BSC_USDC_MAINNET_ADDRESS", "").strip() or BINANCE_PEG_USDC
    slh = os.getenv("SLH_BSC_SLH_TOKEN_ADDRESS", "").strip() or SLH
    wbnb = os.getenv("SLH_BSC_WBNB_ADDRESS", "").strip() or WBNB
    return {
        "name": cfg["name"],
        "chain_id": cfg["chain_id"],
        "rpc_url": cfg["rpc_url"],
        "router": _checksum_address(router, field="router"),
        "wbnb": _checksum_address(wbnb, field="wbnb"),
        "usdc": _checksum_address(usdc, field="usdc"),
        "slh": _checksum_address(slh, field="slh"),
    }


def _require() -> dict[str, Any]:
    from core.bsc_execution import execution_enabled, mainnet_allowed

    if not execution_enabled():
        raise ValueError("BSC_EXECUTION_DISABLED")
    if not mainnet_allowed():
        raise ValueError("BSC_MAINNET_EXECUTION_DISABLED")
    cfg = _cfg()
    if cfg["chain_id"] != 56:
        raise ValueError("BSC_CHAIN_MUST_BE_56")
    return cfg


def policy_snapshot() -> dict[str, Any]:
    try:
        cfg = _cfg()
        enabled = os.getenv("SLH_BSC_EXECUTION_ENABLED", "0").strip() == "1"
        mainnet = os.getenv("SLH_BSC_EXECUTION_ALLOW_MAINNET", "0").strip() == "1"
        return {
            "enabled": enabled and mainnet,
            "network": cfg["name"],
            "chain_id": cfg["chain_id"],
            "router": cfg["router"],
            "wbnb": cfg["wbnb"],
            "usdc": cfg["usdc"],
            "slh": cfg["slh"],
            "usdc_label": "Binance-Peg USDC",
            "broadcast": False,
            "custody": False,
        }
    except Exception as exc:
        return {"enabled": False, "error": type(exc).__name__}


def _token_decimals(web3: Web3, token: str) -> int:
    raw = web3.eth.call({"to": token, "data": "0x" + DECIMALS})
    value = int(raw.hex(), 16)
    if value < 0 or value > 36:
        raise ValueError("TOKEN_DECIMALS_INVALID")
    return value


def _token_balance(web3: Web3, token: str, owner: str) -> int:
    raw = web3.eth.call({"to": token, "data": "0x" + BALANCE_OF + owner[2:].lower().zfill(64)})
    return int(raw.hex(), 16)


def _allowance(web3: Web3, token: str, owner: str, spender: str) -> int:
    data = "0x" + ALLOWANCE + encode(["address", "address"], [owner, spender]).hex()
    return int(web3.eth.call({"to": token, "data": data}).hex(), 16)


def _parse_units(value: str, decimals: int) -> int:
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("INVALID_AMOUNT") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("INVALID_AMOUNT")
    if amount.as_tuple().exponent < -decimals:
        raise ValueError("TOO_MANY_DECIMALS")
    raw = int(amount * (Decimal(10) ** decimals))
    if raw <= 0:
        raise ValueError("INVALID_AMOUNT")
    return raw


def _parse_slippage(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_SLIPPAGE_BPS:
        raise ValueError("INVALID_SLIPPAGE_BPS")
    return value


def _quote(web3: Web3, router: str, path: list[str], amount_in_raw: int) -> list[int]:
    if amount_in_raw <= 0:
        raise ValueError("INVALID_AMOUNT")
    data = "0x" + GET_AMOUNTS_OUT + encode(
        ["uint256", "address[]"], [amount_in_raw, path]
    ).hex()
    raw = web3.eth.call({"to": router, "data": data})
    decoded = list(__import__("eth_abi").decode(["uint256[]"], raw))[0]
    values = [int(x) for x in decoded]
    if len(values) != len(path):
        raise ValueError("INVALID_QUOTE_RESPONSE")
    return values


def _min_out(amount_out_raw: int, slippage_bps: int) -> int:
    return (amount_out_raw * (10_000 - slippage_bps)) // 10_000


def _approval_tx(web3: Web3, sender: str, token: str, spender: str, amount_raw: int) -> dict[str, Any] | None:
    if _allowance(web3, token, sender, spender) >= amount_raw:
        return None
    data = "0x" + APPROVE + encode(["address", "uint256"], [spender, amount_raw]).hex()
    gas = int(web3.eth.estimate_gas({"from": sender, "to": token, "value": 0, "data": data}))
    return {
        "from": sender,
        "to": token,
        "value": "0x0",
        "data": data,
        "gas": _hex_quantity(gas),
        "gasPrice": _hex_quantity(int(web3.eth.gas_price)),
    }


def _base_result(cfg: dict[str, Any], sender: str, trade: str, path: list[str], amount_in_raw: int,
                 amount_out_raw: int, amount_out_min: int, amount_in: str, amount_out: str,
                 decimals_out: int, block_number: int) -> dict[str, Any]:
    return {
        "ok": True,
        "trade": trade,
        "network": cfg["name"],
        "chain_id": cfg["chain_id"],
        "router": cfg["router"],
        "from": sender,
        "path": path,
        "amount_in_raw": amount_in_raw,
        "amount_in": amount_in,
        "amount_out_raw": amount_out_raw,
        "amount_out": amount_out,
        "minimum_out_raw": amount_out_min,
        "output_decimals": decimals_out,
        "block_number": block_number,
        "broadcast": False,
    }


def quote(uid: str, trade: str, amount: str) -> dict[str, Any]:
    cfg = _require()
    web3 = _client(cfg)
    sender = _bound_account(uid)
    trade = str(trade).upper()
    if trade == "BNB_USDC":
        inp, out, din, dout = cfg["wbnb"], cfg["usdc"], 18, _token_decimals(web3, cfg["usdc"])
        amount_raw = _parse_units(amount, din)
        paths = [[inp, out]]
    elif trade == "USDC_BNB":
        inp, out, din, dout = cfg["usdc"], cfg["wbnb"], _token_decimals(web3, cfg["usdc"]), 18
        amount_raw = _parse_units(amount, din)
        paths = [[inp, out]]
    elif trade == "BNB_SLH":
        inp, out, din, dout = cfg["wbnb"], cfg["slh"], 18, _token_decimals(web3, cfg["slh"])
        amount_raw = _parse_units(amount, din)
        paths = [[inp, out]]
    elif trade == "SLH_BNB":
        inp, out, din, dout = cfg["slh"], cfg["wbnb"], _token_decimals(web3, cfg["slh"]), 18
        amount_raw = _parse_units(amount, din)
        paths = [[inp, out]]
    elif trade == "USDC_SLH":
        inp, out = cfg["usdc"], cfg["slh"]
        din, dout = _token_decimals(web3, cfg["usdc"]), _token_decimals(web3, cfg["slh"])
        amount_raw = _parse_units(amount, din)
        paths = [[inp, out], [inp, cfg["wbnb"], out]]
    elif trade == "SLH_USDC":
        inp, out = cfg["slh"], cfg["usdc"]
        din, dout = _token_decimals(web3, cfg["slh"]), _token_decimals(web3, cfg["usdc"])
        amount_raw = _parse_units(amount, din)
        paths = [[inp, out], [inp, cfg["wbnb"], out]]
    else:
        raise ValueError("UNSUPPORTED_SWAP_PAIR")

    last_error = None
    for path in paths:
        try:
            values = _quote(web3, cfg["router"], path, amount_raw)
            return _base_result(
                cfg, sender, trade, path, amount_raw, values[-1], values[-1],
                str(Decimal(amount_raw) / Decimal(10 ** din)),
                str(Decimal(values[-1]) / Decimal(10 ** dout)),
                dout, int(web3.eth.block_number),
            )
        except Exception as exc:
            last_error = exc
    raise ValueError("NO_LIQUIDITY_ROUTE") from last_error


def prepare(uid: str, trade: str, amount: str, slippage_bps: int, deadline_seconds: int = 1200) -> dict[str, Any]:
    cfg = _require()
    if not 60 <= int(deadline_seconds) <= 3600:
        raise ValueError("INVALID_DEADLINE_SECONDS")
    slip = _parse_slippage(slippage_bps)
    q = quote(uid, trade, amount)
    web3 = _client(cfg)
    sender = _bound_account(uid)
    path = q["path"]
    amount_in_raw = q["amount_in_raw"]
    amount_out_raw = q["amount_out_raw"]
    amount_out_min = _min_out(amount_out_raw, slip)
    deadline = int(__import__("time").time()) + int(deadline_seconds)
    fees = _fee_fields(web3)
    max_fee = int(fees["maxFeePerGas"], 16)
    gas_tx: dict[str, Any]
    approval = None

    if trade in {"BNB_USDC", "BNB_SLH"}:
        data = "0x" + SWAP_EXACT_ETH_FOR_TOKENS + encode(
            ["uint256", "address[]", "address", "uint256"],
            [amount_out_min, path, sender, deadline],
        ).hex()
        gas = int(web3.eth.estimate_gas({"from": sender, "to": cfg["router"], "value": amount_in_raw, "data": data}))
        required = amount_in_raw + gas * max_fee
        balance = int(web3.eth.get_balance(sender))
        if balance < required:
            raise BSCExecutionError("INSUFFICIENT_NATIVE_GAS", available=balance, required_for_value=amount_in_raw, estimated_gas=gas, estimated_fee_raw=gas * max_fee)
        gas_tx = {
            "from": sender, "to": cfg["router"], "value": _hex_quantity(amount_in_raw),
            "data": data, "gas": _hex_quantity(gas), "gas_limit": _hex_quantity(gas),
            "nonce": _hex_quantity(int(web3.eth.get_transaction_count(sender, "pending"))),
            "chainId": _hex_quantity(cfg["chain_id"]), **fees,
        }
    elif trade in {"USDC_BNB", "SLH_BNB"}:
        token = cfg["usdc"] if trade == "USDC_BNB" else cfg["slh"]
        approval = _approval_tx(web3, sender, token, cfg["router"], amount_in_raw)
        token_balance = _token_balance(web3, token, sender)
        if token_balance < amount_in_raw:
            raise ValueError("INSUFFICIENT_TOKEN_BALANCE")
        data = "0x" + SWAP_EXACT_TOKENS_FOR_ETH + encode(
            ["uint256", "uint256", "address[]", "address", "uint256"],
            [amount_in_raw, amount_out_min, path, sender, deadline],
        ).hex()
        gas = int(web3.eth.estimate_gas({"from": sender, "to": cfg["router"], "value": 0, "data": data}))
        approval_gas = int(approval["gas"], 16) if approval else 0
        native_balance = int(web3.eth.get_balance(sender))
        if native_balance < (gas + approval_gas) * max_fee:
            raise ValueError("INSUFFICIENT_BNB_FOR_GAS")
        gas_tx = {
            "from": sender, "to": cfg["router"], "value": "0x0", "data": data,
            "gas": _hex_quantity(gas), "gas_limit": _hex_quantity(gas),
            "nonce": _hex_quantity(int(web3.eth.get_transaction_count(sender, "pending"))),
            "chainId": _hex_quantity(cfg["chain_id"]), **fees,
        }
    elif trade in {"USDC_SLH", "SLH_USDC"}:
        offer_token = cfg["usdc"] if trade == "USDC_SLH" else cfg["slh"]
        approval = _approval_tx(web3, sender, offer_token, cfg["router"], amount_in_raw)
        token_balance = _token_balance(web3, offer_token, sender)
        if token_balance < amount_in_raw:
            raise ValueError("INSUFFICIENT_TOKEN_BALANCE")
        data = "0x" + SWAP_EXACT_TOKENS_FOR_TOKENS + encode(
            ["uint256", "uint256", "address[]", "address", "uint256"],
            [amount_in_raw, amount_out_min, path, sender, deadline],
        ).hex()
        gas = int(web3.eth.estimate_gas({"from": sender, "to": cfg["router"], "value": 0, "data": data}))
        approval_gas = int(approval["gas"], 16) if approval else 0
        native_balance = int(web3.eth.get_balance(sender))
        if native_balance < (gas + approval_gas) * max_fee:
            raise ValueError("INSUFFICIENT_BNB_FOR_GAS")
        gas_tx = {
            "from": sender, "to": cfg["router"], "value": "0x0", "data": data,
            "gas": _hex_quantity(gas), "gas_limit": _hex_quantity(gas),
            "nonce": _hex_quantity(int(web3.eth.get_transaction_count(sender, "pending"))),
            "chainId": _hex_quantity(cfg["chain_id"]), **fees,
        }
    else:
        raise ValueError("UNSUPPORTED_SWAP_PAIR")

    q.update({
        "minimum_out_raw": amount_out_min,
        "slippage_bps": slip,
        "deadline": deadline,
        "approval": approval,
        "tx": gas_tx,
        "estimated_fee_raw": int(web3.eth.gas_price) * int(gas_tx["gas"], 16),
        "approval_required": approval is not None,
        "approval_required_exact": amount_in_raw if approval else 0,
    })
    return q
