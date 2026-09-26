import unittest
from pathlib import Path


class WalletAndAcademyUiContractTests(unittest.TestCase):
    def test_wallet_copy_is_binding_aware_not_globally_paused(self):
        source = Path("handlers/wallet_handler.py").read_text(encoding="utf-8")
        self.assertNotIn("מושהים כרגע עד להשלמת user-binding מאומת", source)
        self.assertIn("get_binding", source)
        self.assertIn("get_ton_binding", source)
        self.assertIn("deposits_are_open", source)

    def test_mini_app_has_no_staking_academy_prerequisite_claim(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertNotIn("כדי לפתוח Staking: התחל קורס", source)
        self.assertIn("Academy הוא מסלול למידה נפרד", source)

    def test_ton_challenge_uses_canonical_manifest_domain(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertNotIn("const domain=window.location.hostname", source)
        self.assertIn("slh-cloud-bot-production.up.railway.app/tonconnect-manifest.json", source)

    def test_ton_connect_manifest_is_valid_and_preserves_proof_domain(self):
        source = Path("webapp.py").read_text(encoding="utf-8")
        self.assertIn('@app.route("/tonconnect-manifest.json")', source)
        self.assertIn('"url": "https://slh-nft.com"', source)
        self.assertIn('"iconUrl": "https://slh-nft.com/icon-192.png"', source)
        self.assertNotIn('iconUrl": "https://slh-nft.com/img/logo.svg', source)

    def test_ton_connect_does_not_redirect_to_noncanonical_bot(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertNotIn("SLH_AIR_bot", source)

    def test_ton_connect_surfaces_proof_and_connection_errors(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertIn("proofItem?.error", source)
        self.assertIn("tonProof error", source)
        self.assertIn("connect error", source)
        self.assertIn("TON_CONNECT_ERROR", source)


if __name__ == "__main__":
    unittest.main()
