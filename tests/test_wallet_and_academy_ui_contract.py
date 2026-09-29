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
        self.assertIn("slh-nft.com/tonconnect-manifest.json", source)

    def test_ton_connect_has_sign_data_fallback(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertIn("signData", source)
        self.assertIn("/api/wallet/ton/sign-data/verify", source)
        self.assertIn("ton_sign_data", Path("core/ton_wallet_binding.py").read_text(encoding="utf-8"))



    def test_mini_app_refreshes_telegram_session_on_resume_and_retries_auth(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertIn("visibilitychange", source)
        self.assertIn("window.addEventListener('focus'", source)
        self.assertIn("__slhResumeTelegramSession", source)
        self.assertIn("loadMe(false)", source)
        self.assertIn("X-Telegram-Init-Data", Path("webapp.py").read_text(encoding="utf-8"))

    def test_ton_connect_does_not_redirect_to_noncanonical_bot(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertNotIn("SLH_AIR_bot", source)


if __name__ == "__main__":
    unittest.main()
