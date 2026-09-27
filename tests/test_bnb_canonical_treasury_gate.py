import os
import unittest
from unittest.mock import patch
from core.bnb_gate import bnb_readiness


class BnbCanonicalTreasuryGateTests(unittest.TestCase):
    def cfg(self, treasury="0x1111111111111111111111111111111111111111"):
        return {
            "network": "bsc",
            "rpc": "https://example.invalid",
            "chain_id": 56,
            "confirmations": 15,
            "treasury_wallet": treasury,
        }

    def test_gate_is_closed_without_explicit_canonical_treasury(self):
        with patch.dict(os.environ, {"BNB_DEPOSITS_OPEN": "1"}, clear=False), patch(
            "core.bnb_gate._effective_config", return_value=self.cfg()
        ):
            status = bnb_readiness()
        self.assertFalse(status["effective_open"])
        self.assertIn("BNB_CANONICAL_TREASURY_MISSING", status["reasons"])

    def test_gate_requires_matching_canonical_treasury(self):
        with patch.dict(
            os.environ,
            {
                "BNB_DEPOSITS_OPEN": "1",
                "SLH_BSC_CANONICAL_TREASURY": self.cfg()["treasury_wallet"],
            },
            clear=False,
        ), patch("core.bnb_gate._effective_config", return_value=self.cfg()):
            status = bnb_readiness()
        self.assertTrue(status["effective_open"])

    def test_gate_closes_on_mismatch(self):
        with patch.dict(
            os.environ,
            {
                "BNB_DEPOSITS_OPEN": "1",
                "SLH_BSC_CANONICAL_TREASURY": "0x2222222222222222222222222222222222222222",
            },
            clear=False,
        ), patch("core.bnb_gate._effective_config", return_value=self.cfg()):
            status = bnb_readiness()
        self.assertFalse(status["effective_open"])
        self.assertIn("BNB_CANONICAL_TREASURY_MISMATCH", status["reasons"])


if __name__ == "__main__":
    unittest.main()
