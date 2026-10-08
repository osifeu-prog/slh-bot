import unittest
from pathlib import Path


class TestSlhBrowserSendContract(unittest.TestCase):
    def test_owner_send_uses_external_browser(self):
        source = Path("handlers/slh_handler.py").read_text(encoding="utf-8")
        self.assertIn("url=browser_url", source)
        self.assertIn("MetaMask / Trezor", source)
        self.assertIn("_owner_slh_browser_send_url(uid, recipient, amount)", source)

    def test_browser_flow_has_authenticated_verify_and_settle_routes(self):
        webapp = Path("webapp.py").read_text(encoding="utf-8")
        html = Path("slh_browser_send.html").read_text(encoding="utf-8")
        self.assertIn('/api/v1/wallet/slh/browser-send-config', webapp)
        self.assertIn('/api/v1/wallet/slh/browser-send/verify', webapp)
        self.assertIn('/api/v1/wallet/slh/browser-send/settle', webapp)
        self.assertIn('/api/v1/wallet/slh/browser-send-config?', html)
        self.assertIn('/api/v1/wallet/slh/browser-send/verify', html)
        self.assertIn('/api/v1/wallet/slh/browser-send/settle', html)
        self.assertIn('settlement_to_internal', html)


if __name__ == "__main__":
    unittest.main()
