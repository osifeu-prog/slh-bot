import json

from core.asset_registry import all_assets, get_asset
from core.tokenomics import snapshot


def test_asset_registry_has_real_settlement_flags():
    assets = all_assets()
    assert assets["SLH"]["tradable"] is True
    assert assets["CREDITS"]["tradable"] is False
    assert assets["TON"]["tradable"] is False
    assert assets["BNB"]["tradable"] is False
    assert get_asset("slh")["symbol"] == "SLH"


def test_tokenomics_has_no_minting_path_claim():
    data = snapshot()
    assert data["SLH"]["minting_supported"] is False
    assert data["SLH"]["on_chain"] is False


def test_revenue_ledger_module_compiles():
    import core.revenue_ledger as revenue_ledger
    assert callable(revenue_ledger.record)
    assert callable(revenue_ledger.summary)
