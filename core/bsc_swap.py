"""Safe BSC swap quote and transaction preparation.

This module does not hold keys, sign, broadcast, or mutate internal balances.
It prepares a user-signed PancakeSwap V2 transaction for BNB <-> USDT and SLH <-> BNB.
"""
from __future__ import annotations

import os
import time
from decimal import Decimal, InvalidOperation
from typing import Any

from eth_abi import encode
from web3 import Web3

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
    BSCExecutionError,
    ZERO_ADDRESS,
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
        "slh_default": "0x0000000000000000000000000000000000000000",
    },
    "bsc-mainnet": {
        "router": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
        "wbnb": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        "usdt_env": "SLH_BSC_USDT_MAINNET_ADDRESS",
        "slh_default": "0xACb0A09414CEA1C879c67bB7A877E4e19480f022",
    },
}

MAX_SLIPPAGE_BPS = 1_000
DEFAULT_DEADLINE_SECONDS = 1_200
SLH_MAX_TRADE_FRACTION_ENV = "SLH_BSC_SWAP_MAX_TRADE_FRACTION_BPS"
SLH_MIN_WBNB_RESERVE_ENV = "SLH_BSC_SWAP_MIN_WBNB_RESERVE"
SLH_MIN_SLH_RESERVE_ENV = "SLH_BSC_SWAP_MIN_SLH_RESERVE"


def _decode_uint256(raw: bytes) -> int:
    return int(raw.hex(), 16)


def _cfg() -> dict[str, Any]:
    """Use the canonical execution-layer network config, including its RPC URL."""
    exec_cfg = _network()
    name = exec_cfg["name"]
    router = os.getenv("SLH_BSC_PANCAKE_V2_ROUTER", "").strip() or DEFAULTS[name]["router"]
    wbnb = os.getenv("SLH_BSC_WBNB_ADDRESS", "").strip() or DEFAULTS[name]["wbnb"]
    usdt = os.getenv(DEFAULTS[name]["usdt_env"], "").strip()
    slh = os.getenv("SLH_BSC_SLH_TOKEN_ADDRESS", "").strip() or (
        DEFAULTS[name]["slh_default"] if name == "bsc-mainnet" else ""
    )

    return {
        "name": name,
        "chain_id": exec_cfg["chain_id"],
        "rpc_url": exec_cfg["rpc_url"],
        "router": _checksum_address(router, field="router"),
        "wbnb": _checksum_address(wbnb, field="token"),
        "usdt": _checksum_address(usdt, field="token") if usdt else None,
        "slh": _checksum_address(slh, field="token") if slh else None,
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
        "slh_configured": bool(cfg["slh"]),
        "broadcast": False,
        "custody": False,
        "liquidity_policy_configured": all(
            os.getenv(k, "").strip()
            for k in (
                SLH_MAX_TRADE_FRACTION_ENV,
                SLH_MIN_WBNB_RESERVE_ENV,
                SLH_MIN_SLH_RESERVE_ENV,
            )
        ),
    }


def _require_enabled() -> dict[str, Any]:
    cfg = _cfg()
    if not execution_enabled():
        raise ValueError("BSC_EXECUTION_DISABLED")
    return cfg


def _env_decimal(name: str) -> Decimal | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"INVALID_{name}") from exc
    if not value.is_finite() or value <= 0:
        raise ValueError(f"INVALID_{name}")
    return value


def _liquidity_policy() -> dict[str, Decimal]:
    max_fraction = _env_decimal(SLH_MAX_TRADE_FRACTION_ENV)
    min_wbnb = _env_decimal(SLH_MIN_WBNB_RESERVE_ENV)
    min_slh = _env_decimal(SLH_MIN_SLH_RESERVE_ENV)
    if max_fraction is None or min_wbnb is None or min_slh is None:
        raise ValueError("SLH_SWAP_LIQUIDITY_POLICY_MISSING")
    if max_fraction > Decimal("10000"):
        raise ValueError("INVALID_SLH_SWAP_MAX_TRADE_FRACTION_BPS")
    return {
        "max_trade_fraction_bps": max_fraction,
        "min_wbnb_reserve": min_wbnb,
        "min_slh_reserve": min_slh,
    }


def _pair_state(web3, router: str, token_a: str, token_b: str) -> dict[str, Any]:
    router_contract = web3.eth.contract(
        address=router,
        abi=[{
            "inputs": [],
            "name": "factory",
            "outputs": [{"type": "address"}],
            "stateMutability": "view",
            "type": "function",
        }],
    )
    factory = router_contract.functions.factory().call()
    factory_contract = web3.eth.contract(
        address=factory,
        abi=[{
            "inputs": [
                {"type": "address", "name": "tokenA"},
                {"type": "address", "name": "tokenB"},
            ],
            "name": "getPair",
            "outputs": [{"type": "address"}],
            "stateMutability": "view",
            "type": "function",
        }],
    )
    pair_address = factory_contract.functions.getPair(token_a, token_b).call()
    pair_address = Web3.to_checksum_address(pair_address)
    if pair_address.lower() == ZERO_ADDRESS.lower():
        raise ValueError("SLH_WBNB_PAIR_NOT_FOUND")
    pair = web3.eth.contract(
        address=pair_address,
        abi=[
            {"inputs": [], "name": "token0", "outputs": [{"type": "address"}],
             "stateMutability": "view", "type": "function"},
            {"inputs": [], "name": "token1", "outputs": [{"type": "address"}],
             "stateMutability": "view", "type": "function"},
            {"inputs": [], "name": "getReserves",
             "outputs": [{"type": "uint112"}, {"type": "uint112"}, {"type": "uint32"}],
             "stateMutability": "view", "type": "function"},
        ],
    )
    token0 = Web3.to_checksum_address(pair.functions.token0().call())
    token1 = Web3.to_checksum_address(pair.functions.token1().call())
    reserve0, reserve1, _ = pair.functions.getReserves().call()
    slh_raw = int(reserve0 if token0.lower() == token_a.lower() else reserve1)
    wbnb_raw = int(reserve0 if token0.lower() == token_b.lower() else reserve1)
    return {
        "pair": pair_address,
        "slh_reserve_raw": slh_raw,
        "wbnb_reserve_raw": wbnb_raw,
        "slh_reserve": Decimal(slh_raw) / Decimal(10**15),
        "wbnb_reserve": Decimal(wbnb_raw) / Decimal(10**18),
        "block_number": int(web3.eth.block_number),
    }


def _guard_slh_wbnb_liquidity(
    web3,
    cfg: dict[str, Any],
    *,
    amount_in_raw: int,
    input_decimals: int,
    amount_out_raw: int,
    output_decimals: int,
) -> dict[str, Any]:
    policy = _liquidity_policy()
    state = _pair_state(web3, cfg["router"], cfg["slh"], cfg["wbnb"])
    if state["wbnb_reserve"] < policy["min_wbnb_reserve"]:
        raise ValueError("SLH_SWAP_MIN_WBNB_LIQUIDITY_NOT_MET")
    if state["slh_reserve"] < policy["min_slh_reserve"]:
        raise ValueError("SLH_SWAP_MIN_SLH_LIQUIDITY_NOT_MET")
    input_reserve_raw = state["slh_reserve_raw"] if input_decimals == 15 else state["wbnb_reserve_raw"]
    fraction_bps = (Decimal(amount_in_raw) * Decimal(10000)) / Decimal(input_reserve_raw)
    if fraction_bps > policy["max_trade_fraction_bps"]:
        raise ValueError("SLH_SWAP_TRADE_TOO_LARGE_FOR_LIQUIDITY")
    in_units = Decimal(amount_in_raw) / Decimal(10**input_decimals)
    out_units = Decimal(amount_out_raw) / Decimal(10**output_decimals)
    slh_per_wbnb = (
        Decimal(state["slh_reserve_raw"]) / Decimal(10**15)
    ) / (
        Decimal(state["wbnb_reserve_raw"]) / Decimal(10**18)
    )
    spot = (
        Decimal(1) / slh_per_wbnb
        if input_decimals == 15
        else slh_per_wbnb
    )
    fee_adjusted_spot = spot * Decimal("0.997")
    execution_ratio = out_units / in_units
    impact = max(Decimal(0), Decimal(1) - (execution_ratio / fee_adjusted_spot)) if fee_adjusted_spot > 0 else Decimal(1)
    return {
        "pair": state["pair"],
        "reserves": {"slh": str(state["slh_reserve"]), "wbnb": str(state["wbnb_reserve"])},
        "trade_fraction_bps": str(fraction_bps),
        "estimated_price_impact_bps": str(impact * Decimal(10000)),
        "policy": {
            "max_trade_fraction_bps": str(policy["max_trade_fraction_bps"]),
            "min_wbnb_reserve": str(policy["min_wbnb_reserve"]),
            "min_slh_reserve": str(policy["min_slh_reserve"]),
        },
        "block_number": state["block_number"],
    }


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


def quote_bnb_slh(uid: str, amount_bnb: str) -> dict[str, Any]:
    cfg = _require_enabled()
    if not cfg["slh"]:
        raise ValueError("BSC_SLH_NOT_CONFIGURED")
    web3 = _client(cfg)
    sender = _bound_account(uid)
    slh_decimals = _token_decimals(web3, cfg["slh"])
    amount_in_raw = _parse_units(amount_bnb, 18)
    amounts = _quote_raw(web3, cfg["router"], [cfg["wbnb"], cfg["slh"]], amount_in_raw)
    return {
        "ok": True, "trade": "BNB_SLH", "network": cfg["name"], "chain_id": cfg["chain_id"],
        "router": cfg["router"], "from": sender, "token_in": cfg["wbnb"], "token_out": cfg["slh"],
        "token_out_decimals": slh_decimals, "amount_in_raw": amount_in_raw,
        "amount_in": str(Decimal(amount_in_raw) / Decimal(10**18)),
        "amount_out_raw": amounts[-1],
        "amount_out": str(Decimal(amounts[-1]) / Decimal(10**slh_decimals)),
        "path": [cfg["wbnb"], cfg["slh"]], "block_number": int(web3.eth.block_number),
        "quoted_at": int(time.time()), "broadcast": False,
    }


def quote_slh_bnb(uid: str, amount_slh: str) -> dict[str, Any]:
    cfg = _require_enabled()
    if not cfg["slh"]:
        raise ValueError("BSC_SLH_NOT_CONFIGURED")
    web3 = _client(cfg)
    sender = _bound_account(uid)
    slh_decimals = _token_decimals(web3, cfg["slh"])
    amount_in_raw = _parse_units(amount_slh, slh_decimals)
    amounts = _quote_raw(web3, cfg["router"], [cfg["slh"], cfg["wbnb"]], amount_in_raw)
    return {
        "ok": True, "trade": "SLH_BNB", "network": cfg["name"], "chain_id": cfg["chain_id"],
        "router": cfg["router"], "from": sender, "token_in": cfg["slh"], "token_out": cfg["wbnb"],
        "token_out_decimals": 18, "amount_in_raw": amount_in_raw,
        "amount_in": str(Decimal(amount_in_raw) / Decimal(10**slh_decimals)),
        "amount_out_raw": amounts[-1],
        "amount_out": str(Decimal(amounts[-1]) / Decimal(10**18)),
        "path": [cfg["slh"], cfg["wbnb"]], "block_number": int(web3.eth.block_number),
        "quoted_at": int(time.time()), "broadcast": False,
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
        raise BSCExecutionError("INSUFFICIENT_NATIVE_GAS", available=native_balance, required_for_value=amount_in_raw, estimated_gas=None)
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
        raise BSCExecutionError(
            "INSUFFICIENT_NATIVE_GAS",
            available=native_balance,
            required_for_value=amount_in_raw,
            estimated_gas=gas,
            estimated_fee_raw=gas * max_fee,
        )
    nonce = int(web3.eth.get_transaction_count(sender, "pending"))
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
        "nonce": nonce,
        "tx": {
            "from": sender,
            "to": cfg["router"],
            "value": _hex_quantity(amount_in_raw),
            "data": _encode_swap_exact_eth_for_tokens(
                amount_out_min, [cfg["wbnb"], cfg["usdt"]], sender, deadline
            ),
            "gas": _hex_quantity(gas),
            "gas_limit": _hex_quantity(gas),
            "nonce": _hex_quantity(nonce),
            "chainId": _hex_quantity(cfg["chain_id"]),
            **fees,
        },
        "estimated_fee_raw": gas * max_fee,
        "broadcast": False,
        "approval_required": False,
    }


def _prepare_slh_to_bnb_common(uid: str, amount_slh: str, slippage_bps: int, *, deadline_seconds: int) -> dict[str, Any]:
    cfg = _require_enabled()
    if not cfg["slh"]:
        raise ValueError("BSC_SLH_NOT_CONFIGURED")
    web3 = _client(cfg)
    sender = _bound_account(uid)
    slh_decimals = _token_decimals(web3, cfg["slh"])
    amount_in_raw = _parse_units(amount_slh, slh_decimals)
    amounts = _quote_raw(web3, cfg["router"], [cfg["slh"], cfg["wbnb"]], amount_in_raw)
    amount_out_raw = amounts[-1]
    amount_out_min = _amount_out_min(amount_out_raw, slippage_bps)
    deadline = _deadline(deadline_seconds)
    liquidity = _guard_slh_wbnb_liquidity(
        web3, cfg, amount_in_raw=amount_in_raw, input_decimals=slh_decimals,
        amount_out_raw=amount_out_raw, output_decimals=18
    )
    token_balance = _decode_uint256(web3.eth.call({
        "to": cfg["slh"], "data": "0x" + ERC20_BALANCE_OF_SELECTOR + sender[2:].lower().zfill(64)
    }))
    if token_balance < amount_in_raw:
        raise ValueError("INSUFFICIENT_SLH_BALANCE")
    allowance = _decode_uint256(web3.eth.call({
        "to": cfg["slh"],
        "data": "0x" + ERC20_ALLOWANCE_SELECTOR + encode(["address", "address"], [sender, cfg["router"]]).hex(),
    }))
    approval = None
    if allowance < amount_in_raw:
        approval_gas = int(web3.eth.estimate_gas({
            "from": sender, "to": cfg["slh"], "value": 0,
            "data": _encode_approve(cfg["router"], amount_in_raw),
        }))
        approval = {
            "from": sender, "to": cfg["slh"], "value": "0x0",
            "data": _encode_approve(cfg["router"], amount_in_raw),
            "gas": _hex_quantity(approval_gas), "gasPrice": _hex_quantity(int(web3.eth.gas_price)),
            "chainId": _hex_quantity(cfg["chain_id"]),
        }
    gas_data = _encode_swap_exact_tokens_for_eth(
        amount_in_raw, amount_out_min, [cfg["slh"], cfg["wbnb"]], sender, deadline
    )
    swap_gas = int(web3.eth.estimate_gas({
        "from": sender, "to": cfg["router"], "value": 0, "data": gas_data
    }))
    gas_price = int(web3.eth.gas_price)
    native_balance = int(web3.eth.get_balance(sender))
    total_gas = swap_gas + (int(approval["gas"], 16) if approval else 0)
    if native_balance < total_gas * gas_price:
        raise ValueError("INSUFFICIENT_BNB_FOR_GAS")
    return {
        "ok": True, "trade": "SLH_BNB", "network": cfg["name"], "chain_id": cfg["chain_id"],
        "router": cfg["router"], "from": sender, "recipient": sender,
        "amount_in_raw": amount_in_raw, "amount_in": str(Decimal(amount_in_raw) / Decimal(10**slh_decimals)),
        "quoted_out_raw": amount_out_raw, "minimum_out_raw": amount_out_min,
        "slippage_bps": slippage_bps, "deadline": deadline, "approval": approval,
        "liquidity": liquidity,
        "tx": {
            "from": sender, "to": cfg["router"], "value": "0x0", "data": gas_data,
            "gas": _hex_quantity(swap_gas), "gas_limit": _hex_quantity(swap_gas),
            "chainId": _hex_quantity(cfg["chain_id"]),
            "nonce": _hex_quantity(int(web3.eth.get_transaction_count(sender, "pending"))),
            "gasPrice": _hex_quantity(gas_price),
        },
        "estimated_fee_raw": swap_gas * gas_price, "broadcast": False,
        "approval_required": approval is not None,
    }


def prepare_bnb_to_slh(uid: str, amount_bnb: str, slippage_bps: int, *, deadline_seconds: int = DEFAULT_DEADLINE_SECONDS) -> dict[str, Any]:
    cfg = _require_enabled()
    if not cfg["slh"]:
        raise ValueError("BSC_SLH_NOT_CONFIGURED")
    web3 = _client(cfg)
    sender = _bound_account(uid)
    slh_decimals = _token_decimals(web3, cfg["slh"])
    amount_in_raw = _parse_units(amount_bnb, 18)
    amounts = _quote_raw(web3, cfg["router"], [cfg["wbnb"], cfg["slh"]], amount_in_raw)
    amount_out_raw = amounts[-1]
    amount_out_min = _amount_out_min(amount_out_raw, slippage_bps)
    deadline = _deadline(deadline_seconds)
    liquidity = _guard_slh_wbnb_liquidity(
        web3, cfg, amount_in_raw=amount_in_raw, input_decimals=18,
        amount_out_raw=amount_out_raw, output_decimals=slh_decimals
    )
    native_balance = int(web3.eth.get_balance(sender))
    gas_data = _encode_swap_exact_eth_for_tokens(
        amount_out_min, [cfg["wbnb"], cfg["slh"]], sender, deadline
    )
    gas = int(web3.eth.estimate_gas({
        "from": sender, "to": cfg["router"], "value": hex(amount_in_raw), "data": gas_data
    }))
    fees = _fee_fields(web3)
    max_fee = int(fees["maxFeePerGas"], 16)
    required_native = amount_in_raw + gas * max_fee
    if native_balance < required_native:
        raise BSCExecutionError(
            "INSUFFICIENT_NATIVE_GAS", available=native_balance,
            required_for_value=amount_in_raw, estimated_gas=gas, estimated_fee_raw=gas * max_fee
        )
    nonce = int(web3.eth.get_transaction_count(sender, "pending"))
    return {
        "ok": True, "trade": "BNB_SLH", "network": cfg["name"], "chain_id": cfg["chain_id"],
        "router": cfg["router"], "from": sender, "recipient": sender,
        "amount_in_raw": amount_in_raw, "amount_in": str(Decimal(amount_in_raw) / Decimal(10**18)),
        "quoted_out_raw": amount_out_raw, "minimum_out_raw": amount_out_min,
        "slippage_bps": slippage_bps, "deadline": deadline, "nonce": nonce, "liquidity": liquidity,
        "tx": {
            "from": sender, "to": cfg["router"], "value": _hex_quantity(amount_in_raw), "data": gas_data,
            "gas": _hex_quantity(gas), "gas_limit": _hex_quantity(gas), "nonce": _hex_quantity(nonce),
            "chainId": _hex_quantity(cfg["chain_id"]), **fees,
        },
        "estimated_fee_raw": gas * max_fee, "broadcast": False, "approval_required": False,
    }


def prepare_slh_to_bnb(uid: str, amount_slh: str, slippage_bps: int, *, deadline_seconds: int = DEFAULT_DEADLINE_SECONDS) -> dict[str, Any]:
    return _prepare_slh_to_bnb_common(uid, amount_slh, slippage_bps, deadline_seconds=deadline_seconds)


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
