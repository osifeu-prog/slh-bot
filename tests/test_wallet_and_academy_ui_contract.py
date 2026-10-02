import unittest
from pathlib import Path


class WalletAndAcademyUiContractTests(unittest.TestCase):
    def test_wallet_copy_is_binding_aware_not_globally_paused(self):
        source = Path("handlers/wallet_handler.py").read_text(encoding="utf-8")
        self.assertNotIn("מושהים כרגע עד להשלמת user-binding מאומת", source)
        self.assertIn("get_binding", source)
        self.assertIn("get_ton_binding", source)
        self.assertIn("TON_DEPOSITS_OPEN", source)

    def test_mini_app_has_no_staking_academy_prerequisite_claim(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertNotIn("כדי לפתוח Staking: התחל קורס", source)
        self.assertIn("Academy הוא מסלול למידה נפרד", source)

    def test_ton_challenge_uses_canonical_manifest_domain(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertNotIn("const domain=window.location.hostname", source)
        self.assertNotIn("domain:window.location.hostname", source)
        self.assertIn("body:JSON.stringify({domain:'slh-nft.com'})", source)
        self.assertIn("slh-nft.com/tonconnect-manifest.json", source)

    def test_ton_connect_has_sign_data_fallback(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertIn("signData", source)
        self.assertIn("/api/wallet/ton/sign-data/verify", source)
        self.assertIn("ton_sign_data", Path("core/ton_wallet_binding.py").read_text(encoding="utf-8"))


    def test_ton_connect_does_not_redirect_to_noncanonical_bot(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertNotIn("SLH_AIR_bot", source)

    def test_bnb_ui_uses_canonical_live_binding_renderer(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertIn("function renderBnbWalletState(bnb)", source)
        self.assertIn("const depositsOpen=data.deposits_open===true;", source)
        self.assertIn("renderBnbWalletState(bnb);", source)
        self.assertIn("renderBnbWalletUnavailable();", source)
        self.assertIn("WalletConnect ו־MetaMask זמינים למסלול חיבור ואימות בעלות.", source)
        self.assertIn("BNB Deposit · STAGED", source)
        self.assertIn("BNB Deposit · LIVE", source)
        self.assertNotIn("initialBnbBinding", source)
        self.assertNotIn("const bb=w.bnb_binding||null;", source)
        self.assertNotIn("החיבור וה־Binding פתוחים עכשיו.", source)
        self.assertNotIn("אינו מופעל בתוך Telegram Mini App", source)
    def test_bnb_walletconnect_telegram_uses_manual_uri_flow(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertIn("showQrModal:false,", source)
        self.assertIn('id="bnbWcUriWrap"', source)
        self.assertIn("_walletConnectProvider.on?.('display_uri',uri=>", source)
        self.assertIn("WalletConnect URI נוצר", source)
        self.assertNotIn("showQrModal:true,", source)

    def test_bnb_ux_runtime_does_not_overwrite_canonical_mini_status(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertIn("var bnbConnected=bnb.includes('✅ מאומת')||bnb.includes('🔒 מאומת');", source)
        self.assertIn("uxBnbMini is rendered by renderBnbWalletState(); do not overwrite it here.", source)
        self.assertNotIn("mini.textContent=bnb.includes('✅')?'✅ מאומת':'התחבר כדי לאמת'", source)
    def test_alpha_global_open_is_not_user_eligibility_override(self):
        source = Path("webapp.py").read_text(encoding="utf-8")
        self.assertIn('alpha["global_status"]', source)
        self.assertIn('alpha["global_readiness_status"]', source)
        self.assertNotIn('alpha["status"] = "OPEN"', source)

    def test_mini_app_distinguishes_global_alpha_from_user_eligibility(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertIn("const globalStatus=a.global_status||'CLOSED';", source)
        self.assertIn("const personalStatus=a.status||'review';", source)
        self.assertIn("Alpha global", source)
        self.assertIn("Eligibility", source)

    def test_referral_share_uses_canonical_reward_policy(self):
        source = Path("handlers/share_handler.py").read_text(encoding="utf-8")
        self.assertIn("from core import referral_reward", source)
        self.assertIn("referral_reward.progress(uid)", source)
        self.assertNotIn("0.9 Credits +10 Points", source)

if __name__ == "__main__":
    unittest.main()


    def test_bnb_wallet_connect_supports_metamask_connect_and_trust_dapp_browser(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertIn("@metamask/connect-evm@2.1.1/+esm", source)
        self.assertIn("createEVMClient", source)
        self.assertIn("client.connect({chainIds:['0x38']})", source)
        self.assertIn("personal_sign", source)
        self.assertIn("window.trustwallet?.ethereum", source)
        self.assertIn("link.trustwallet.com/open_url", source)
        self.assertIn("MetaMask — Connect & Verify", source)
        self.assertIn("פתח SLH OS בתוך Trust Wallet", source)
        self.assertIn("חבר Trust Wallet, MetaMask Mobile וארנקים תואמים", source) if "חבר Trust Wallet, MetaMask Mobile וארנקים תואמים" in source else None
        self.assertIn("openBnbInExternalBrowser", source)
        self.assertIn("url:window.location.origin", source)
        self.assertIn("session timeout", source)
        self.assertIn("tg?.openLink(deepLink)", source)

    def test_bnb_tx_provider_prefers_verified_universal_provider(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertIn("if(__slhBnbProvider)return __slhBnbProvider;", source)
        self.assertIn("if(window.trustwallet?.ethereum)return window.trustwallet.ethereum;", source)
