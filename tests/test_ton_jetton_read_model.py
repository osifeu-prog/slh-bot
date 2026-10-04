import unittest
from unittest.mock import Mock, patch

from core.ton_jetton_read_model import list_jetton_balances


class TONJettonReadModelTests(unittest.TestCase):
    def test_requires_verified_ton_wallet(self):
        with patch("core.ton_jetton_read_model.get_ton_binding", return_value=None):
            with self.assertRaisesRegex(ValueError, "TON_WALLET_NOT_VERIFIED"):
                list_jetton_balances("8789977826")

    def test_reads_and_normalizes_balances_without_mutation(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "balances": [
                {
                    "balance": "1234500",
                    "jetton": {
                        "address": "0:abc",
                        "name": "Example",
                        "symbol": "EX",
                        "decimals": 6,
                        "verification": "whitelist",
                    },
                }
            ]
        }

        with patch(
            "core.ton_jetton_read_model.get_ton_binding",
            return_value={"uid": "8789977826", "chain": "ton", "address_raw": "0:" + "11" * 32},
        ), patch(
            "core.ton_jetton_read_model.requests.get",
            return_value=response,
        ):
            result = list_jetton_balances("8789977826")

        self.assertTrue(result["ok"])
        self.assertTrue(result["read_only"])
        self.assertEqual(result["chain"], "ton")
        self.assertEqual(result["balances"][0]["symbol"], "EX")
        self.assertEqual(result["balances"][0]["balance"], "1.2345")


if __name__ == "__main__":
    unittest.main()
