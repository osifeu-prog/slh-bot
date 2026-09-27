import unittest
from pathlib import Path


class MiniAppRegressionTests(unittest.TestCase):
    def setUp(self):
        self.source = Path("mini_app.html").read_text(encoding="utf-8")

    def test_eth_estimate_gas_expression_is_well_formed(self):
        broken = (
            "const gasRaw=_hexBigInt(await provider.request({method:'eth_estimateGas',"
            "params:[{from:account,to:SLH_BSC_TOKEN_ADDRESS,data,value:'0x0'}]));"
        )
        expected = (
            "const gasRaw=_hexBigInt(await provider.request({method:'eth_estimateGas',"
            "params:[{from:account,to:SLH_BSC_TOKEN_ADDRESS,data,value:'0x0'}]}));"
        )
        self.assertNotIn(broken, self.source)
        self.assertIn(expected, self.source)

    def test_command_bridge_routes_known_actions_without_send_data_or_clipboard(self):
        start = self.source.find("function sendCommand(cmd,label){")
        self.assertGreaterEqual(start, 0, "sendCommand function not found")
        end = self.source.find("\nfunction ", start + 1)
        body = self.source[start:] if end < 0 else self.source[start:end]
        self.assertNotIn("tg.sendData", body)
        self.assertNotIn("navigator.clipboard", body)
        for command, screen in (
            ("/wallet", "wallet"),
            ("/transfer", "transfer"),
            ("/stake", "stake"),
            ("/alpha", "alpha"),
            ("/academy", "academy"),
            ("/exchange", "exchange"),
        ):
            self.assertIn(f'"{command}"', body)
            self.assertIn(f'"{screen}"', body)


if __name__ == "__main__":
    unittest.main()
