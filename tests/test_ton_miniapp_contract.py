import unittest
from pathlib import Path


class TonMiniAppContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = Path("mini_app.html").read_text(encoding="utf-8")

    def test_ton_proof_uses_canonical_domain(self):
        self.assertIn("const SLH_TON_PROOF_DOMAIN='slh-nft.com';", self.html)
        self.assertIn("body:JSON.stringify({domain:SLH_TON_PROOF_DOMAIN})", self.html)

    def test_ton_deposit_check_is_available_in_mini_app(self):
        self.assertIn('id="tonTxHash"', self.html)
        self.assertIn('id="tonClaimButton"', self.html)
        self.assertIn("async function checkTonDeposit()", self.html)
        self.assertIn("'/api/wallet/ton/check'", self.html)

    def test_ton_deposit_ui_is_disabled_when_settlement_is_closed(self):
        self.assertIn("⛔ הפקדות TON סגורות כרגע.", self.html)
        self.assertIn("if(!ton.deposits_open)", self.html)


if __name__ == "__main__":
    unittest.main()
