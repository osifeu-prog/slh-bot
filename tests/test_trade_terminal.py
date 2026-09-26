from core import trade_terminal


def test_dex_urls_are_chain_specific():
    assert "uniswap.org/swap?chain=ethereum" in trade_terminal.dex_url("ethereum", "0xabc")
    assert "uniswap.org/swap?chain=base" in trade_terminal.dex_url("base", "0xabc")
    assert "pancakeswap.finance/swap?chain=bsc" in trade_terminal.dex_url("bsc", "0xabc")
    assert trade_terminal.dex_url("solana", "So111111") == "https://jup.ag/swap/SOL-So111111"


def test_execution_fee_defaults_to_zero(monkeypatch):
    monkeypatch.delenv("SLH_TRADE_EXECUTION_FEE_BPS", raising=False)
    assert trade_terminal.execution_fee_bps() == 0


def test_six_languages_exist():
    assert {"he", "en", "ar", "es", "ru", "pt"} <= set(trade_terminal._TEXT)


def test_trade_ui_has_ai_explanation_and_localized_execution_strings():
    for lang in ("he", "en", "ar", "es", "ru", "pt"):
        assert "ai_explain" in trade_terminal._TEXT[lang]
        assert "execution_connector" in trade_terminal._TEXT[lang]
        assert "verified" in trade_terminal._TEXT[lang]
        assert "not_verified" in trade_terminal._TEXT[lang]


def test_trade_scanner_labels_are_localized():
    for lang in ("he", "en", "ar", "es", "ru", "pt"):
        for key in (
            "buy_with_stars",
            "chain_label",
            "dex_label",
            "price_usd_label",
            "change_24h_label",
            "liquidity_label",
            "volume_label",
            "scanner_note",
            "token_fallback",
        ):
            assert key in trade_terminal._TEXT[lang]
