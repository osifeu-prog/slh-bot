"""Single source of product tokenomics for UI/reporting.

Values here describe the current runtime model; they do not mint or allocate
funds. Runtime balances remain authoritative in state/db.json.
"""

from core.stars_price_authority import CREDIT_PACKS


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
            f"{pack.stars}_stars": pack.credits for pack in CREDIT_PACKS
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
    data = {key: dict(value) for key, value in TOKENOMICS.items()}

    # A capability existing in code is not the same as a settlement gate being open.
    try:
        from core.bnb_gate import bnb_readiness
        bnb = bnb_readiness()
        data["BNB"]["deposit_capable"] = True
        data["BNB"]["deposit_supported"] = bool(bnb["effective_open"])
        data["BNB"]["settlement_open"] = bool(bnb["effective_open"])
    except Exception:
        data["BNB"]["deposit_capable"] = True
        data["BNB"]["deposit_supported"] = False
        data["BNB"]["settlement_open"] = False

    try:
        from core.ton_deposit_service import deposits_are_open
        ton_open = bool(deposits_are_open())
        data["TON"]["deposit_capable"] = True
        data["TON"]["deposit_supported"] = ton_open
        data["TON"]["settlement_open"] = ton_open
    except Exception:
        data["TON"]["deposit_capable"] = True
        data["TON"]["deposit_supported"] = False
        data["TON"]["settlement_open"] = False

    data["SLH"]["market_scope"] = "internal_orderbook"
    data["SLH"]["public_dex_trading"] = False
    return data


REWARDS = {
    "join_points": 1000,
    "referral_points": 10,
    "lesson_complete_points": 25,
    "course_complete_points": 250,
}


def rewards_snapshot():
    from core.holiday_campaign import GRANT_AMOUNT
    d = dict(REWARDS)
    d["airdrop_slh"] = GRANT_AMOUNT
    return d
