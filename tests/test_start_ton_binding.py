import unittest
from pathlib import Path


class StartShowsVerifiedTonTest(unittest.TestCase):
    def test_start_reads_verified_binding(self):
        src = Path("handlers/onboarding_v2.py").read_text(encoding="utf-8")
        self.assertIn("get_ton_binding", src)
        self.assertIn("_ton_label(user_id, wallet)", src)
        self.assertNotIn("f\"💎 TON Wallet: {wallet.get('ton_wallet') or 'לא מקושר'}\\n\\n\"", src)


if __name__ == "__main__":
    unittest.main()
