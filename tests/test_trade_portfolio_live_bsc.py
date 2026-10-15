from handlers import trade_terminal_handler as handler


class CaptureBot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))


def _patch_portfolio_dependencies(monkeypatch, live_bsc, api_slh=0):
    from core import profile_manager, wallet_binding, ton_wallet_binding, slh_api_client, bsc_wallet_read_model

    monkeypatch.setattr(
        profile_manager,
        "get_user",
        lambda uid: {"wallet": {"credits": "29.082775", "staked": 794}},
    )
    monkeypatch.setattr(wallet_binding, "get_binding", lambda uid: {"address": "bound"})
    monkeypatch.setattr(ton_wallet_binding, "get_ton_binding", lambda uid: {"address": "ton-bound"})
    monkeypatch.setattr(
        slh_api_client,
        "get_balances",
        lambda uid: {"balances": {"SLH": api_slh}},
    )
    monkeypatch.setattr(bsc_wallet_read_model, "read_bsc_wallet", lambda uid: live_bsc)
    monkeypatch.setattr(
        handler.trade,
        "t",
        lambda key, uid: {"portfolio": "Portfolio", "verified": "verified", "not_verified": "not verified"}.get(key, key),
    )


def test_portfolio_uses_live_bsc_balance_and_labels_api_ledger_separately(monkeypatch):
    _patch_portfolio_dependencies(
        monkeypatch,
        {
            "ok": True,
            "block_number": 126500000,
            "assets": {
                "SLH": {"amount": "988"},
                "BNB": {"amount": "0.0129758603"},
            },
        },
        api_slh=0,
    )
    bot = CaptureBot()

    handler._send_portfolio(bot, 123, "8789977826")

    text = bot.messages[0][1]
    assert "SLH on-chain (BSC): 988" in text
    assert "BSC block 126500000" in text
    assert "SLH API ledger (separate, not on-chain): 0" in text
    assert "SLH on-chain (BSC): 0" not in text


def test_portfolio_shows_unavailable_not_zero_when_live_bsc_read_fails(monkeypatch):
    _patch_portfolio_dependencies(
        monkeypatch,
        {"ok": False, "reason": "TOKEN_READ_FAILED"},
        api_slh=0,
    )
    bot = CaptureBot()

    handler._send_portfolio(bot, 123, "8789977826")

    text = bot.messages[0][1]
    assert "SLH on-chain (BSC): לא זמין" in text
    assert "SLH API ledger (separate, not on-chain): 0" in text
    assert "SLH on-chain (BSC): 0" not in text
