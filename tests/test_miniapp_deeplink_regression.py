import unittest
from pathlib import Path


class MiniAppDeepLinkRegressionTest(unittest.TestCase):
    def test_start_param_and_allowlist_present(self):
        src = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertIn("start_param", src)
        self.assertIn("'academy'", src)
        self.assertIn("allowed.indexOf(raw)", src)
        self.assertIn("typeof window.show==='function'", src)

    def test_horizontal_overflow_is_blocked(self):
        src = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertIn("overflow-x:hidden", src)
        self.assertIn(".app{width:100%;min-width:0", src)

    def test_owner_quick_send_route_contract(self):
        src = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertIn("slh_quick_send", src)
        self.assertIn("owner_to_tzvika_1", src)
        self.assertIn("loadQuickSlhSendPreset", src)
        self.assertIn("startQuickSlhSend", src)
        self.assertIn("Trezor / WalletConnect", src)


if __name__ == "__main__":
    unittest.main()
