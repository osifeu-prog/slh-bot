"""Canonical user-facing asset metadata.

This registry describes what SLH OS currently recognizes. It must stay aligned
with the runtime tokenomics and with the deployed BSC SLH token facts.
"""

SLH_BSC_CHAIN_ID = 56
SLH_BSC_TOKEN_CONTRACT = "0xACb0A09414CEA1C879c67bB7A877E4e19480f022"
SLH_BSC_TOKEN_DECIMALS = 15

ASSETS = {
    "CREDITS": {
        "symbol": "C",
        "name": "SLH Credits",
        "class": "internal_credit",
        "transferable": True,
        "tradable": False,
        "on_chain": False,
        "role": "internal_accounting_unit",
    },
    "SLH": {
        "symbol": "SLH",
        "name": "SLH Token",
        "class": "token",
        "transferable": True,
        "tradable": True,
        "on_chain": True,
        "chain": "bsc",
        "chain_id": SLH_BSC_CHAIN_ID,
        "contract_address": SLH_BSC_TOKEN_CONTRACT,
        "decimals": SLH_BSC_TOKEN_DECIMALS,
        "internal_ledger": True,
        "role": "tradeable_token",
        "settlement": "handlers.exchange_handler",
        "on_chain_deposit_path": "core.slh_deposit_service",
    },
    "TON": {
        "symbol": "TON",
        "name": "TON",
        "class": "external_asset",
        "transferable": True,
        "tradable": False,
        "on_chain": True,
        "deposit_path": "core.ton_deposit_service",
    },
    "BNB": {
        "symbol": "BNB",
        "name": "BNB",
        "class": "external_asset",
        "transferable": True,
        "tradable": False,
        "on_chain": True,
        "chain": "bsc",
        "chain_id": 56,
        "deposit_path": "core.bnb_deposit_service",
    },
}


def all_assets():
    return {k: dict(v) for k, v in ASSETS.items()}


def get_asset(symbol):
    return dict(ASSETS[symbol.upper()]) if symbol.upper() in ASSETS else None
