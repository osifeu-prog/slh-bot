"""Canonical user-facing asset metadata.

This registry describes what SLH OS currently recognizes. It deliberately does
not claim that an asset is tradable unless a real settlement path exists.
"""

ASSETS = {
    "CREDITS": {
        "symbol": "C",
        "name": "SLH Credits",
        "class": "internal_credit",
        "transferable": False,
        "tradable": False,
        "on_chain": False,
    },
    "SLH": {
        "symbol": "SLH",
        "name": "SLH Token",
        "class": "internal_token",
        "transferable": True,
        "tradable": True,
        "settlement": "handlers.exchange_handler",
        "on_chain": False,
    },
    "TON": {
        "symbol": "TON",
        "name": "TON",
        "class": "external_asset",
        "transferable": True,
        "tradable": False,
        "deposit_path": "core.economy_service.record_ton_deposit",
        "on_chain": True,
    },
    "BNB": {
        "symbol": "BNB",
        "name": "BNB",
        "class": "external_asset",
        "transferable": True,
        "tradable": False,
        "on_chain": True,
    },
}


def all_assets():
    return {k: dict(v) for k, v in ASSETS.items()}


def get_asset(symbol):
    return dict(ASSETS[symbol.upper()]) if symbol.upper() in ASSETS else None
