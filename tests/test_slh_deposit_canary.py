import unittest
from unittest.mock import patch

from core import slh_deposit_service


class SlhDepositCanaryTests(unittest.TestCase):
    def _verified(self, address):
        return {
            "ok": True,
            "tx_hash": "0xabc",
            "from": address,
            "to": "0x9999999999999999999999999999999999999999",
            "amount_slh": 1.0,
            "raw_amount": 1,
            "decimals": 0,
            "block": 123,
            "confirmations": 15,
            "required_confirmations": 15,
            "token_contract": "0x8888888888888888888888888888888888888888",
            "treasury_wallet": "0x9999999999999999999999999999999999999999",
        }

    def test_configured_slh_canary_can_settle_when_public_slh_gate_is_closed(self):
        db = {
            "users": {
                "owner": {"wallet": {"token_balance": 0.0, "live_token_balance": 0.0}}
            }
        }
        address = "0x1111111111111111111111111111111111111111"

        with patch.object(slh_deposit_service, "slh_settlement_allowed", return_value=True),              patch.object(slh_deposit_service, "get_binding", return_value={"address": address}),              patch.object(slh_deposit_service, "verify_slh_deposit", return_value=self._verified(address)),              patch.object(slh_deposit_service.state_manager, "atomic_update", side_effect=lambda fn: fn(db)):
            result = slh_deposit_service.settle_slh_deposit("owner", "0xabc")

        self.assertEqual(result["status"], "applied")
        self.assertEqual(result["live_token_balance"], 1.0)
        self.assertEqual(result["token_balance"], 1.0)
        self.assertEqual(db["users"]["owner"]["wallet"]["live_token_balance"], 1.0)

    def test_closed_gate_without_canary_rejects_before_verification(self):
        with patch.object(slh_deposit_service, "slh_settlement_allowed", return_value=False),              patch.object(slh_deposit_service, "get_binding") as get_binding:
            with self.assertRaisesRegex(ValueError, "SLH_SETTLEMENT_CLOSED"):
                slh_deposit_service.settle_slh_deposit("owner", "0xabc")
            get_binding.assert_not_called()


if __name__ == "__main__":
    unittest.main()
