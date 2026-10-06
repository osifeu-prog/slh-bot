from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from handlers import slh_handler


def test_parse_slh_amount_allows_contract_precision():
    assert slh_handler._parse_amount("1") == "1"
    assert slh_handler._parse_amount("1.000000000000001") == "1.000000000000001"


def test_parse_slh_amount_rejects_over_precision():
    try:
        slh_handler._parse_amount("1.0000000000000001")
    except ValueError as exc:
        assert str(exc) == "INVALID_SLH_AMOUNT"
    else:
        raise AssertionError("expected INVALID_SLH_AMOUNT")


def test_mini_app_url_prefills_route():
    url = slh_handler._mini_app_url(
        screen="wallet",
        slh_route="smoke",
        slh_smoke="1",
        recipient="0x1111111111111111111111111111111111111111",
        amount="1",
    )
    assert "screen=wallet" in url
    assert "slh_route=smoke" in url
    assert "slh_smoke=1" in url
    assert "amount=1" in url
    assert "recipient=0x1111111111111111111111111111111111111111" in url


def test_status_uses_live_bsc_truth_and_active_registry():
    binding = {
        "uid": "501",
        "chain": "bsc",
        "address": "0x1111111111111111111111111111111111111111",
    }
    registry = {
        "uid": "501",
        "status": "active",
        "per_tx_limit_slh": "1",
        "daily_limit_slh": "1",
        "mode": "user_signed_only",
    }
    live = {
        "ok": True,
        "assets": {
            "BNB": {"amount": "0.01499"},
            "SLH": {"amount": "1000000"},
        },
    }
    with patch.object(slh_handler, "get_binding", return_value=binding), \
         patch.object(slh_handler, "get_secondary_distribution_wallet", return_value=registry), \
         patch.object(slh_handler, "read_bsc_wallet", return_value=live):
        text, got_binding, got_registry, got_live = slh_handler._status("501")

    assert got_binding == binding
    assert got_registry == registry
    assert got_live == live
    assert "SLH on-chain: 1,000,000" in text
    assert "BNB gas: 0.01499" in text
    assert "Per-tx: 1 SLH" in text
    assert "Daily: 1 SLH" in text


def test_trust_wallet_smoke_url_uses_one_time_handoff():
    handoff = {"token": "smoke-token-12345678901234567890"}
    with patch.object(slh_handler, "create_handoff", return_value=handoff):
        url = slh_handler._trust_wallet_smoke_url("5010371391")

    parts = urlsplit(url)
    assert parts.scheme == "https"
    assert parts.netloc == "link.trustwallet.com"
    outer = parse_qs(parts.query)
    assert outer["coin_id"] == ["20000714"]
    assert len(outer["url"]) == 1

    target = urlsplit(outer["url"][0])
    assert target.path == "/wallet-handoff"
    inner = parse_qs(target.query)
    assert inner["next"] == ["/slh-smoke"]
    assert inner["code"] == ["smoke-token-12345678901234567890"]


def test_owner_menu_includes_quick_send_to_tzvika():
    binding = {
        "uid": "8789977826",
        "chain": "bsc",
        "address": "0x1111111111111111111111111111111111111111",
    }
    live = {
        "ok": True,
        "assets": {
            "BNB": {"amount": "0.01"},
            "SLH": {"amount": "1"},
        },
    }
    quick = {
        "ok": True,
        "label": "צביקה",
        "sender": "0x1111111111111111111111111111111111111111",
        "recipient": "0x2222222222222222222222222222222222222222",
        "recipient_uid": "5010371391",
        "amount_slh": "1",
        "chain_id": 56,
        "token_contract": "0xACb0A09414CEA1C879c67bB7A877E4e19480f022",
        "signing": "user_wallet_only",
        "custody": False,
    }
    with patch.object(slh_handler, "get_binding", return_value=binding), \
         patch.object(slh_handler, "get_secondary_distribution_wallet", return_value=None), \
         patch.object(slh_handler, "read_bsc_wallet", return_value=live), \
         patch.object(slh_handler, "get_quick_send_config", return_value=quick):
        text, markup = slh_handler._menu("8789977826", include_test=True)

    buttons = [button for row in markup.keyboard for button in row]
    quick_buttons = [b for b in buttons if "שלח 1 SLH" in b.text]
    assert quick_buttons
    assert quick_buttons[0].url.find("/wallet-handoff?") >= 0
    assert "next=%2Fslh-browser-send" in quick_buttons[0].url



def test_owner_browser_send_url_uses_wallet_handoff():
    handoff = {"token": "browser-send-token-1234567890"}
    with patch.object(slh_handler, "create_handoff", return_value=handoff):
        url = slh_handler._owner_slh_browser_send_url("8789977826")

    target = urlsplit(url)
    assert target.path == "/wallet-handoff"
    inner = parse_qs(target.query)
    assert inner["next"] == ["/slh-browser-send"]
    assert inner["code"] == ["browser-send-token-1234567890"]
