import os
import unittest
from unittest.mock import patch

from core import ton_deposit_service as service


CANARY_UID = "12345"
TREASURY = "0:" + "33" * 32


class TonCanaryGateTests(unittest.TestCase):
    def test_configured_canary_is_blocked_by_default_when_public_gate_is_closed(self):
        with patch.object(service, "_settings", return_value=(TREASURY, 100)):
            with patch.dict(
                os.environ,
                {
                    "TON_DEPOSITS_OPEN": "0",
                    "TON_DEPOSITS_CANARY_UID": CANARY_UID,
                    "TON_DEPOSITS_CANARY_SETTLEMENT_OPEN": "0",
                },
                clear=False,
            ):
                self.assertFalse(service.ton_settlement_allowed(CANARY_UID))
                self.assertFalse(service.ton_settlement_allowed("99999"))

    def test_canary_needs_both_uid_match_and_explicit_settlement_enable(self):
        with patch.object(service, "_settings", return_value=(TREASURY, 100)):
            with patch.dict(
                os.environ,
                {
                    "TON_DEPOSITS_OPEN": "0",
                    "TON_DEPOSITS_CANARY_UID": CANARY_UID,
                    "TON_DEPOSITS_CANARY_SETTLEMENT_OPEN": "1",
                },
                clear=False,
            ):
                self.assertTrue(service.ton_settlement_allowed(CANARY_UID))
                self.assertFalse(service.ton_settlement_allowed("99999"))

    def test_public_gate_does_not_depend_on_canary_enable_flag(self):
        with patch.object(service, "_settings", return_value=(TREASURY, 100)):
            with patch.dict(
                os.environ,
                {
                    "TON_DEPOSITS_OPEN": "1",
                    "TON_DEPOSITS_CANARY_UID": CANARY_UID,
                    "TON_DEPOSITS_CANARY_SETTLEMENT_OPEN": "0",
                },
                clear=False,
            ):
                self.assertTrue(service.ton_settlement_allowed("99999"))


if __name__ == "__main__":
    unittest.main()
