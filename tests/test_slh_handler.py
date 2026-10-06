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
    with patch.object(slh_handler, "create_handoff", return_value=handoff),          patch.object(slh_handler, "os") as os_mock:
        os_mock.getenv.return_value = "https://slh-cloud-bot-production.up.railway.app/mini-app-v4"
        url = slh_handler._trust_wallet_smoke_url("5010371391")

    assert url.startswith("https://link.trustwallet.com/open_url?coin_id=60&url=")
    assert "wallet-handoff" in url
    assert "next=%2Fslh-smoke" in url
    assert "smoke-token-12345678901234567890" in url
