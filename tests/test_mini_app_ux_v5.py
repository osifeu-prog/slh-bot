from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / "mini_app.html"


def test_expired_telegram_session_has_recovery_ui():
    html = HTML.read_text(encoding="utf-8")
    assert 'id="authGateTitle"' in html
    assert 'id="authGateText"' in html
    assert "TELEGRAM_INIT_DATA_EXPIRED" in html
    assert "reopenMiniApp" in html


def test_wallet_flow_is_labelled_connect_mode():
    html = HTML.read_text(encoding="utf-8")
    assert "CONNECT MODE" in html
    assert "MetaMask — Connect & Verify" in html
    assert "WalletConnect" in html
    assert "TON Connect + TON Proof" in html
