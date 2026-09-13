"""Single source of product tokenomics for UI/reporting.

Values here describe the current runtime model; they do not mint or allocate
funds. Runtime balances remain authoritative in state/db.json.
"""

TOKENOMICS = {
    "SLH": {
        "type": "internal_token",
        "on_chain": False,
        "transferable": True,
        "tradable": True,
        "supply_model": "existing_balances_only",
        "minting_supported": False,
        "notes": "SLH transfers move existing wallet balances; no mint_token path is declared here.",
    },
    "CREDITS": {
        "type": "internal_credit",
        "on_chain": False,
        "transferable": False,
        "tradable": False,
        "supply_model": "ledger_issued",
        "pricing_examples": {
            "100_stars": 100,
            "450_stars": 500,
            "800_stars": 1000,
        },
        "notes": "Credits are the internal settlement unit for products, staking and marketplace activity.",
    },
    "TON": {
        "type": "external_crypto",
        "on_chain": True,
        "deposit_supported": True,
        "tradable": False,
        "notes": "Deposit accounting exists; market trading must not be advertised without a settled path.",
    },
    "BNB": {
        "type": "external_crypto",
        "on_chain": True,
        "wallet_binding_supported": True,
        "deposit_supported": True,
        "tradable": False,
        "notes": "Wallet binding/deposit paths exist; market trading must not be advertised without a settled path.",
    },
}


def snapshot():
    return {key: dict(value) for key, value in TOKENOMICS.items()}
