from pathlib import Path


def test_bnb_walletconnect_uses_reown_appkit_core():
    html = Path("mini_app.html").read_text(encoding="utf-8")
    assert "@reown/appkit@1.8.24/+esm" in html
    assert "@walletconnect/universal-provider@2.25.0/+esm" in html
    assert "manualWCControl:true" in html
    assert "window.location.origin" in html
    assert "optionalNamespaces" in html
    assert "personal_sign" in html


def test_bnb_walletconnect_preserves_server_side_verification():
    html = Path("mini_app.html").read_text(encoding="utf-8")
    assert "/api/wallet/bnb/challenge" in html
    assert "/api/wallet/bnb/verify" in html
    assert "verifyBnbProvider(provider,'WalletConnect')" in html


def test_bnb_walletconnect_stays_separate_from_settlement():
    html = Path("mini_app.html").read_text(encoding="utf-8")
    assert "BNB_DEPOSITS_CLOSED" in html or "Settlement סגור" in html
    assert "broadcast" in html
