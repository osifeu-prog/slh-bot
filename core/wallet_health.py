"""Read-only BSC wallet health inventory.

This is an evidence view, not a compromise detector. It inventories wallets known
to SLH OS through verified bindings, the governed secondary-wallet registry, and
the configured Treasury, then reads live BSC balances. It never signs, broadcasts,
or mutates balances.
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


def _address(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw or not Web3.is_address(raw):
        return None
    return Web3.to_checksum_address(raw)


def _token(web3: Web3, address: str, contract_address: str) -> dict[str, Any]:
    contract = web3.eth.contract(address=contract_address, abi=ERC20_ABI)
    raw = int(contract.functions.balanceOf(address).call())
    decimals = int(contract.functions.decimals().call())
    symbol = str(contract.functions.symbol().call())
    amount = Decimal(raw) / (Decimal(10) ** decimals)
    return {"symbol": symbol, "raw": raw, "amount": str(amount), "decimals": decimals}


def _positive(asset: dict[str, Any] | None) -> bool:
    try:
        return Decimal(str((asset or {}).get("amount") or "0")) > 0
    except Exception:
        return False


def _classify(*, treasury: bool, verified: bool, assets: dict[str, Any], rpc_ok: bool) -> str:
    if not rpc_ok:
        return "RPC_ERROR"
    if treasury:
        return "TREASURY"
    bnb = assets.get("BNB", {})
    slh = assets.get("SLH", {})
    usdt = assets.get("USDT", {})
    if verified and _positive(slh) and not _positive(bnb):
        return "VERIFIED_NEEDS_BNB_GAS"
    if verified and any(_positive(x) for x in (bnb, slh, usdt)):
        return "VERIFIED_FUNDED"
    if verified:
        return "VERIFIED_EMPTY"
    return "UNBOUND_KNOWN_ADDRESS"


def build_wallet_health() -> dict[str, Any]:
    db = state_manager.load_db()
    cfg = _cfg()
    rpc = str(cfg.get("rpc") or "").strip()
    if not rpc:
        return {
            "ok": False,
            "read_only": True,
            "reason": "BSC_RPC_NOT_CONFIGURED",
            "wallets": [],
        }

    web3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 8}))
    if not web3.is_connected():
        return {
            "ok": False,
            "read_only": True,
            "reason": "BSC_RPC_UNAVAILABLE",
            "wallets": [],
        }

    chain_id = int(web3.eth.chain_id)
    if chain_id != 56:
        return {
            "ok": False,
            "read_only": True,
            "reason": "BSC_CHAIN_ID_NOT_56",
            "chain_id": chain_id,
            "wallets": [],
        }

    treasury = _address(cfg.get("treasury_wallet"))
    token_contract = _address(cfg.get("token_contract"))
    usdt_contract = _address(os.getenv("SLH_BSC_USDT_MAINNET_ADDRESS", ""))
    zuz_contract = _address(os.getenv("SLH_BSC_ZUZ_ADDRESS", ""))

    known: dict[str, dict[str, Any]] = {}

    def add(address: Any, source: str, uid: Any = None, role: str | None = None) -> None:
        normalized = _address(address)
        if not normalized:
            return
        key = normalized.lower()
        row = known.setdefault(
            key,
            {
                "address": normalized,
                "uids": [],
                "sources": [],
                "roles": [],
                "binding_verified": False,
                "secondary_active": False,
                "is_treasury": False,
            },
        )
        if uid is not None and str(uid) not in row["uids"]:
            row["uids"].append(str(uid))
        if source not in row["sources"]:
            row["sources"].append(source)
        if role and role not in row["roles"]:
            row["roles"].append(role)
        if role == "treasury":
            row["is_treasury"] = True

    bindings = db.get("wallet_bindings", {}) if isinstance(db, dict) else {}
    for binding in bindings.values() if isinstance(bindings, dict) else []:
        if not isinstance(binding, dict) or binding.get("chain") != "bsc":
            continue
        add(binding.get("address"), "verified_binding", binding.get("uid"), "user")

    secondary = db.get("secondary_distribution_wallets", {}) if isinstance(db, dict) else {}
    for uid, row in secondary.items() if isinstance(secondary, dict) else []:
        if not isinstance(row, dict):
            continue
        add(
            row.get("address"),
            "secondary_registry",
            uid,
            "secondary_distribution" if row.get("status") == "active" else "secondary_revoked",
        )

    if treasury:
        add(treasury, "configured_treasury", None, "treasury")

    rows: list[dict[str, Any]] = []
    for key in sorted(known):
        row = dict(known[key])
        address = row["address"]
        binding = get_binding(row["uids"][0]) if row["uids"] else None
        row["binding_verified"] = bool(binding and str(binding.get("address", "")).lower() == key)
        row["secondary_active"] = "secondary_distribution" in row["roles"]

        try:
            bnb_raw = int(web3.eth.get_balance(address))
            assets: dict[str, Any] = {
                "BNB": {
                    "symbol": "BNB",
                    "raw": bnb_raw,
                    "decimals": 18,
                    "amount": str(Decimal(bnb_raw) / Decimal(10**18)),
                }
            }
            if token_contract:
                try:
                    assets["SLH"] = _token(web3, address, token_contract)
                except Exception:
                    assets["SLH"] = {"symbol": "SLH", "amount": None, "error": "TOKEN_READ_FAILED"}
            if usdt_contract:
                try:
                    assets["USDT"] = _token(web3, address, usdt_contract)
                except Exception:
                    assets["USDT"] = {"symbol": "USDT", "amount": None, "error": "TOKEN_READ_FAILED"}
            if zuz_contract:
                try:
                    assets["ZUZ"] = _token(web3, address, zuz_contract)
                except Exception:
                    assets["ZUZ"] = {"symbol": "ZUZ", "amount": None, "error": "TOKEN_READ_FAILED"}
            row["assets"] = assets
            row["health"] = _classify(
                treasury=row["is_treasury"],
                verified=row["binding_verified"],
                assets=assets,
                rpc_ok=True,
            )
            row["zuz"] = {
                "configured": bool(zuz_contract),
                "needs_budget": bool(
                    zuz_contract
                    and row["secondary_active"]
                    and not _positive(assets.get("ZUZ"))
                ),
            }
            row["security_assessment"] = "SECURITY_REVIEW_NOT_PERFORMED"
        except Exception as exc:
            row["assets"] = {}
            row["health"] = "RPC_ERROR"
            row["error"] = type(exc).__name__
            row["zuz"] = {"configured": bool(zuz_contract), "needs_budget": False}
            row["security_assessment"] = "SECURITY_REVIEW_NOT_PERFORMED"

        rows.append(row)

    summary = {
        "total": len(rows),
        "treasury": sum(1 for x in rows if x["health"] == "TREASURY"),
        "verified_funded": sum(1 for x in rows if x["health"] == "VERIFIED_FUNDED"),
        "verified_needs_bnb_gas": sum(1 for x in rows if x["health"] == "VERIFIED_NEEDS_BNB_GAS"),
        "verified_empty": sum(1 for x in rows if x["health"] == "VERIFIED_EMPTY"),
        "unbound_known": sum(1 for x in rows if x["health"] == "UNBOUND_KNOWN_ADDRESS"),
        "rpc_error": sum(1 for x in rows if x["health"] == "RPC_ERROR"),
        "zuz_budget_needed": sum(1 for x in rows if x.get("zuz", {}).get("needs_budget")),
    }

    return {
        "ok": True,
        "read_only": True,
        "chain": "bsc",
        "chain_id": 56,
        "block_number": int(web3.eth.block_number),
        "zuz_contract_configured": bool(zuz_contract),
        "summary": summary,
        "wallets": rows,
        "security_note": "Balance state alone is not evidence that a wallet is compromised.",
        "source": "state/db.json wallet registry + BSC live RPC",
    }
