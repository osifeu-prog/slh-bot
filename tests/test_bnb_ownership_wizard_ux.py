from pathlib import Path


def test_bnb_ownership_wizard_uses_existing_automatic_signature_flow():
    source = Path("mini_app.html").read_text(encoding="utf-8")

    assert 'id="bnbOwnershipWizard"' in source
    assert 'onclick="startBnbOwnershipWizard()"' in source
    assert 'onclick="startBnbOwnershipViaWalletConnect()"' in source
    assert "לא צריך להעתיק את ה־Nonce, את החתימה או Transaction Hash לטלגרם" in source
    assert "await bindBnbWallet();" in source
    assert "await connectBnbWalletConnect();" in source
    assert "await provider.request({method:'personal_sign',params:[ch.message,address]})" in source
    assert "fetch('/api/wallet/bnb/verify'" in source
    assert "לא נשלחה עסקה" in source
    assert "לא נשלח BNB" in source


def test_bnb_ownership_wizard_remains_inside_telegram_auth_boundary():
    source = Path("mini_app.html").read_text(encoding="utf-8")

    assert "if(!initData)" in source
    assert "showAuthGate();" in source
    assert "fetch('/api/wallet/bnb/challenge'" in source
    assert "fetch('/api/wallet/bnb/verify'" in source
