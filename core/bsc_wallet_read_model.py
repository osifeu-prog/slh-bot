"""Read-only BSC wallet asset truth.

Uses the authenticated user's verified BNB wallet binding and reads live
on-chain balances from BSC. No signing, broadcasting, custody, or DB mutation.
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

from web3 import Web3

import state_manager
from core.binance_connector import get_bsc_config
from core.wallet_binding import get_binding

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
]


def _cfg() -> dict[str, Any]:
    db = state_manager.load_db()
    cfg = dict(get_bsc_config())
    overrides = db.get("bsc_settings") if isinstance(db, dict) else None
    if isinstance(overrides, dict):
        cfg.update(overrides)
    return cfg


def _token_balance(web3: Web3, address: str, token_address: str) -> dict[str, Any]:
    contract = web3.eth.contract(
        address=web3.to_checksum_address(token_address),
        abi=ERC20_ABI,
    )
    raw = int(contract.functions.balanceOf(address).call())
    decimals = int(contract.functions.decimals().call())
    symbol = str(contract.functions.symbol().call())
    amount = Decimal(raw) / (Decimal(10) ** decimals)
    return {
        "address": web3.to_checksum_address(token_address),
        "symbol": symbol,
        "raw": raw,
        "decimals": decimals,
        "amount": str(amount),
    }


def read_bsc_wallet(uid: str) -> dict[str, Any]:
    binding = get_binding(str(uid))
    if not binding:
        return {
            "ok": False,
            "reason": "BNB_WALLET_NOT_VERIFIED",
            "verified": False,
        }

    cfg = _cfg()
    rpc = str(cfg.get("rpc") or "").strip()
    if not rpc:
        return {"ok": False, "reason": "BSC_RPC_NOT_CONFIGURED", "verified": True}

    address = Web3.to_checksum_address(str(binding.get("address") or ""))
    web3 = Web3(Web3.HTTPProvider(rpc))

    chain_id = int(web3.eth.chain_id)
    if chain_id != 56:
        return {
            "ok": False,
            "reason": "BSC_CHAIN_ID_NOT_56",
            "verified": True,
            "wallet": address,
            "chain_id": chain_id,
        }

    block_number = int(web3.eth.block_number)
    bnb_raw = int(web3.eth.get_balance(address))

    assets: dict[str, dict[str, Any]] = {
        "BNB": {
            "symbol": "BNB",
            "raw": bnb_raw,
            "decimals": 18,
            "amount": str(Decimal(bnb_raw) / Decimal(10**18)),
        }
    }

    slh_contract = str(cfg.get("token_contract") or "").strip()
    if slh_contract:
        try:
            assets["SLH"] = _token_balance(web3, address, slh_contract)
        except Exception:
            assets["SLH"] = {
                "symbol": "SLH",
                "address": slh_contract,
                "raw": None,
                "decimals": None,
                "amount": None,
                "error": "TOKEN_READ_FAILED",
            }

    usdt_contract = str(os.getenv("SLH_BSC_USDT_MAINNET_ADDRESS", "")).strip()
    if usdt_contract:
        try:
            assets["USDT"] = _token_balance(web3, address, usdt_contract)
        except Exception:
            assets["USDT"] = {
                "symbol": "USDT",
                "address": usdt_contract,
                "raw": None,
                "decimals": None,
                "amount": None,
                "error": "TOKEN_READ_FAILED",
            }

    return {
        "ok": True,
        "verified": True,
        "wallet": address,
        "network": "bsc",
        "chain_id": chain_id,
        "block_number": block_number,
        "assets": assets,
        "source": "BSC live RPC + verified BNB wallet binding",
        "read_only": True,
    }
