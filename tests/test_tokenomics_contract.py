from core.stars_price_authority import CREDIT_PACKS
from core.tokenomics import (
    SLH_BSC_CHAIN_ID,
    SLH_BSC_TOKEN_CONTRACT,
    SLH_BSC_TOKEN_DECIMALS,
    TOKENOMICS,
)


def test_slh_is_documented_as_on_chain_bsc_token():
    slh = TOKENOMICS["SLH"]
    assert slh["on_chain"] is True
    assert slh["chain_id"] == 56
    assert slh["contract_address"] == "0xACb0A09414CEA1C879c67bB7A877E4e19480f022"
    assert slh["decimals"] == 15
    assert slh["minting_in_slh_os"] is False


def test_credits_are_internal_but_p2p_transferable():
    credits = TOKENOMICS["CREDITS"]
    assert credits["on_chain"] is False
    assert credits["internal_transferable"] is True
    assert credits["tradable_as_asset"] is False
    assert credits["exchange_role"] == "quote_currency"


def test_stars_catalog_matches_canonical_pricing_authority():
    assert [(p.stars, p.credits) for p in CREDIT_PACKS] == [
        (100, 100),
        (500, 550),
        (1000, 1200),
    ]
    assert TOKENOMICS["CREDITS"]["pricing_examples"] == {
        "100_stars": 100,
        "500_stars": 550,
        "1000_stars": 1200,
    }


def test_network_constants_are_lossless_contract_metadata():
    assert SLH_BSC_CHAIN_ID == 56
    assert SLH_BSC_TOKEN_DECIMALS == 15
    assert SLH_BSC_TOKEN_CONTRACT.lower() == "0xacb0a09414cea1c879c67bb7a877e4e19480f022"


def test_bnb_settlement_is_credits_not_slh():
    bnb = TOKENOMICS["BNB"]
    assert bnb["internal_settlement_rate"] == "1000 Credits per BNB"
    assert "not" in bnb["notes"]
    assert "credit SLH" in bnb["notes"]


def test_ton_rate_is_a_safe_band_not_a_hardcoded_live_quote():
    ton = TOKENOMICS["TON"]
    assert ton["internal_settlement_rate_policy"] == "100-110 Credits per TON"
    assert ton["deposit_supported"] is True
