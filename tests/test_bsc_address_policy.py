import os
import unittest
from unittest.mock import patch

BAD_ADDRESS = "0x693db6c817083818696a7228aebfbd0cd3371f02"
OWNER_TREZOR_ADDRESS = "0x468328B2a7C9b5629e87844Bb4531e7409400b34"
TX_HASH = "0x" + "1" * 64


class CompromisedBscAddressPolicyTests(unittest.TestCase):
    def test_forensic_alias_is_zuz_and_address_is_quarantined(self):
        from core.bsc_address_policy import (
            forensic_alias,
            is_quarantined_bsc_address,
        )

        self.assertTrue(is_quarantined_bsc_address(BAD_ADDRESS))
        self.assertTrue(is_quarantined_bsc_address(BAD_ADDRESS.upper().replace("0X", "0x")))
        self.assertEqual(forensic_alias(BAD_ADDRESS), "ZUZ")
        self.assertFalse(is_quarantined_bsc_address(OWNER_TREZOR_ADDRESS))
        self.assertIsNone(forensic_alias(OWNER_TREZOR_ADDRESS))

    def test_bnb_gate_fails_closed_for_quarantined_configured_treasury(self):
        from core.bnb_gate import bnb_readiness

        cfg = {
            "network": "bsc",
            "rpc": "https://example.invalid",
            "chain_id": 56,
            "confirmations": 15,
            "treasury_wallet": BAD_ADDRESS,
        }
        with patch.dict(
            os.environ,
            {
                "BNB_DEPOSITS_OPEN": "1",
                "SLH_BSC_CANONICAL_TREASURY": BAD_ADDRESS,
            },
            clear=False,
        ), patch("core.bnb_gate._effective_config", return_value=cfg):
            status = bnb_readiness()

        self.assertFalse(status["ready"])
        self.assertFalse(status["effective_open"])
        self.assertIn("BNB_TREASURY_QUARANTINED_ZUZ", status["reasons"])
        self.assertIn("BNB_CANONICAL_TREASURY_QUARANTINED_ZUZ", status["reasons"])

    def test_wallet_binding_refuses_quarantined_address_without_db_mutation(self):
        from core import wallet_binding

        db = {}
        with patch(
            "core.wallet_binding.state_manager.atomic_update",
            side_effect=lambda mutate: mutate(db),
        ):
            with self.assertRaisesRegex(ValueError, "BSC_ADDRESS_QUARANTINED_ZUZ"):
                wallet_binding.issue_challenge("test-user", BAD_ADDRESS)

        self.assertEqual(db, {})

    def test_bsc_execution_refuses_quarantined_transfer_recipient(self):
        from core.bsc_execution import _checksum_address

        with self.assertRaisesRegex(ValueError, "BSC_ADDRESS_QUARANTINED_ZUZ"):
            _checksum_address(BAD_ADDRESS, field="recipient")

    def test_bnb_deposit_verification_refuses_quarantined_treasury_before_rpc(self):
        from core import deposit_monitor

        cfg = {
            "network": "bsc",
            "rpc": "https://example.invalid",
            "chain_id": 56,
            "confirmations": 15,
            "treasury_wallet": BAD_ADDRESS,
            "token_contract": "0xACb0A09414CEA1C879c67bB7A877E4e19480f022",
        }
        with patch("core.deposit_monitor.get_bsc_config", return_value=cfg), patch(
            "core.deposit_monitor.state_manager.load_db",
            return_value={"bsc_settings": {"treasury_wallet": BAD_ADDRESS}},
        ), patch("core.deposit_monitor.Web3.HTTPProvider") as provider:
            result = deposit_monitor.verify_bnb_deposit(TX_HASH)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "BSC_ADDRESS_QUARANTINED_ZUZ")
        provider.assert_not_called()

    def test_slh_deposit_verification_refuses_quarantined_treasury_before_rpc(self):
        from core import slh_deposit_service

        cfg = {
            "network": "bsc",
            "rpc": "https://example.invalid",
            "chain_id": 56,
            "confirmations": 15,
            "treasury_wallet": BAD_ADDRESS,
            "token_contract": "0xACb0A09414CEA1C879c67bB7A877E4e19480f022",
        }
        with patch("core.slh_deposit_service._config", return_value=cfg), patch(
            "core.slh_deposit_service.Web3.HTTPProvider"
        ) as provider:
            result = slh_deposit_service.verify_slh_deposit(TX_HASH)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "BSC_ADDRESS_QUARANTINED_ZUZ")
        provider.assert_not_called()

    def test_owner_slh_send_handoff_refuses_quarantined_recipient(self):
        from core.identity import OWNER_TELEGRAM_ID
        from handlers import slh_handler

        with patch("handlers.slh_handler.create_handoff") as create_handoff:
            with self.assertRaisesRegex(ValueError, "BSC_ADDRESS_QUARANTINED_ZUZ"):
                slh_handler._owner_slh_browser_send_url(
                    OWNER_TELEGRAM_ID,
                    BAD_ADDRESS,
                    "1",
                )
        create_handoff.assert_not_called()


if __name__ == "__main__":
    unittest.main()
