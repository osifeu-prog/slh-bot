"""Canonical SLH OS tokenomics for UI/reporting.

This file describes the currently implemented accounting boundaries. Runtime
balances remain authoritative in state/db.json; on-chain facts come from the
configured chain/RPC and the deployed contracts.

Important: Credits and SLH are distinct in the current runtime. Renaming or
merging them would be a separate economic migration, not a presentation fix.
"""

from core.stars_price_authority import CREDIT_PACKS


SLH_BSC_CHAIN_ID = 56
SLH_BSC_TOKEN_CONTRACT = "0xACb0A09414CEA1C879c67bB7A877E4e19480f022"
SLH_BSC_TOKEN_DECIMALS = 15


TOKENOMICS = {
    "SLH": {
        "type": "token",
        "symbol": "SLH",
        "on_chain": True,
        "internal_ledger": True,
        "internal_transferable": True,
        "on_chain_transferable": True,
        "tradable_internal": True,
        "chain": "bsc",
        "chain_id": SLH_BSC_CHAIN_ID,
        "contract_address": SLH_BSC_TOKEN_CONTRACT,
        "decimals": SLH_BSC_TOKEN_DECIMALS,
        "supply_policy_in_slh_os": "existing_balances_only",
        "minting_in_slh_os": False,
        "minting_supported": False,
        "notes": (
            "SLH exists both as a deployed BSC token and as an internal SLH "
            "ledger used by the exchange/distribution authorities. The OS does "
            "not expose a mint_token path; verified on-chain deposits can "
            "increase an internal SLH balance through the canonical deposit service."
        ),
    },
    "CREDITS": {
        "type": "internal_credit",
        "symbol": "CREDITS",
        "on_chain": False,
        "internal_transferable": True,
        "tradable_as_asset": False,
        "exchange_role": "quote_currency",
        "supply_model": "ledger_issued",
        "pricing_examples": {
            f"{pack.stars}_stars": pack.credits for pack in CREDIT_PACKS
        },
        "notes": (
            "Credits are the internal accounting unit for products, staking, "
            "rewards and the SLH exchange quote side. P2P internal Credit "
            "transfers are supported."
        ),
    },
    "BNB": {
        "type": "external_native_asset",
        "symbol": "BNB",
        "on_chain": True,
        "chain": "bsc",
        "chain_id": SLH_BSC_CHAIN_ID,
        "wallet_binding_supported": True,
        "deposit_supported": True,
        "internal_settlement_rate": "1000 Credits per BNB",
        "tradable_in_slh_exchange": False,
        "notes": (
            "BNB is an external settlement asset. The current BNB deposit path "
            "converts verified inbound BNB into internal Credits; it does not "
            "mint or credit SLH."
        ),
    },
    "TON": {
        "type": "external_native_asset",
        "symbol": "TON",
        "on_chain": True,
        "wallet_binding_supported": True,
        "deposit_supported": True,
        "internal_settlement_rate_policy": "100-110 Credits per TON",
        "tradable_in_slh_exchange": False,
        "notes": (
            "The active TON settlement rate is configuration-controlled inside "
            "the documented safe band; it must be read from runtime configuration "
            "before quoting a live value."
        ),
    },
    "TELEGRAM_STARS": {
        "type": "external_payment_unit",
        "symbol": "XTR",
        "on_chain": False,
        "payment_supported": True,
        "settles_into": "CREDITS / product entitlements",
        "notes": "Stars are an external payment rail, not the SLH token.",
    },
}


def snapshot():
    return {key: dict(value) for key, value in TOKENOMICS.items()}


REWARDS = {
    "join_points": 1000,
    "referral_points": 10,
    "referral_credits": 0.9,
    "lesson_complete_points": 25,
    "course_complete_points": 250,
    "vote_points": 10,
}


def rewards_snapshot():
    from core.holiday_campaign import GRANT_AMOUNT

    d = dict(REWARDS)
    d["airdrop_slh"] = 0
    d["historical_holiday_airdrop_slh"] = GRANT_AMOUNT
    return d
