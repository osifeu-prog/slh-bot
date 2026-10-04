import unittest
from pathlib import Path


class WalletAndAcademyUiContractTests(unittest.TestCase):
    def test_bot_first_wallet_commands_are_registered(self):
        source = Path("handlers/wallet_handler.py").read_text(encoding="utf-8")
        for command in [
            'commands=["wallet_status", "wallet_ops"]',
            'commands=["bnb_gate"]',
            'commands=["bsc_policy"]',
            'commands=["bsc_prepare_bnb"]',
            'commands=["bsc_prepare_slh"]',
            'commands=["bsc_receipt"]',
            'commands=["bnb_sign"]',
            'commands=["connect_bnb", "bnb_challenge"]',
            'commands=["connect_bnb_verify", "bnb_verify"]',
        ]:
            self.assertIn(command, source)

    def test_bot_first_bsc_commands_do_not_accept_secret_material(self):
        source = Path("handlers/wallet_handler.py").read_text(encoding="utf-8")
        lowered = source.lower()

        # The handlers may explain the security boundary in human-readable text.
        # What must be absent is an input/API contract that accepts secret material.
        forbidden_input_contracts = (
            "private_key=",
            "private_key>",
            "seed_phrase=",
            "seed_phrase>",
            "mnemonic=",
            "mnemonic>",
            "secret_key=",
            "secret_key>",
        )
        for marker in forbidden_input_contracts:
            self.assertNotIn(marker, lowered)

        self.assertIn("bot לא מחזיק את המפתח", source)
        self.assertIn("חתום בארנק שלך בלבד", source)

    def test_bnb_web_proof_is_one_time_and_address_bound(self):
        source = Path("core/bnb_web_proof.py").read_text(encoding="utf-8")
        self.assertIn("bnb_web_proof_sessions", source)
        self.assertIn("token_urlsafe(32)", source)
        self.assertIn("SESSION_TTL_SECONDS = 600", source)
        self.assertIn("address", source)
        self.assertIn("expires_at", source)
        self.assertIn("consumed", source)

    def test_bnb_sign_page_uses_personal_sign_and_bsc_chain_56(self):
        source = Path("webapp.py").read_text(encoding="utf-8")
        self.assertIn('/wallet/bnb-sign', source)
        self.assertIn("personal_sign", source)
        self.assertIn("'0x38'", source)
        self.assertIn("/api/wallet/bnb/session/", source)
        self.assertNotIn("private_key=", source.lower())
        self.assertNotIn("seed_phrase=", source.lower())
        self.assertNotIn("mnemonic=", source.lower())

    def test_bsc_execution_remains_external_signer_only(self):
        source = Path("core/bsc_execution.py").read_text(encoding="utf-8")
        self.assertIn("external_signer_only", source)
        self.assertIn("This module never stores private keys", source)

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
