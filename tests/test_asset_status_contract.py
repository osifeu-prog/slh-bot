from pathlib import Path


def test_miniapp_reward_asset_status_is_gate_aware():
    source = Path("mini_app.html").read_text(encoding="utf-8")
    assert 'val.deposit_supported===true' in source
    assert 'val.deposit_capable===true' in source
    assert 'val.market_scope==="internal_orderbook"' in source


def test_tokenomics_uses_live_settlement_state():
    source = Path("core/tokenomics.py").read_text(encoding="utf-8")
    assert 'from core.bnb_gate import bnb_readiness' in source
    assert 'from core.ton_deposit_service import deposits_are_open' in source
