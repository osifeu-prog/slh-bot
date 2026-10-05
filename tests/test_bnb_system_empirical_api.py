import unittest
from unittest.mock import patch

import webapp


class BNBSystemEmpiricalApiTests(unittest.TestCase):
    def setUp(self):
        self.client = webapp.app.test_client()

    def test_empirical_smoke_requires_owner(self):
        with patch("webapp.authenticated_uid", return_value="5010371391"), patch(
            "core.authority.is_owner", return_value=False
        ):
            response = self.client.post(
                "/api/wallet/bnb/empirical-smoke",
                json={"tx_hash": "0x" + "ab" * 32},
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json(), {"error": "BNB_EMPIRICAL_SMOKE_OWNER_ONLY"})

    def test_empirical_smoke_returns_wait_state_before_confirmations(self):
        with patch("webapp.authenticated_uid", return_value="8789977826"), patch(
            "core.authority.is_owner", return_value=True
        ), patch(
            "core.bnb_gate.bnb_deposits_open", return_value=False
        ), patch(
            "core.bnb_gate.bnb_settlement_allowed", return_value=True
        ), patch(
            "core.deposit_monitor.verify_bnb_deposit",
            return_value={
                "ok": False,
                "error": "INSUFFICIENT_CONFIRMATIONS",
                "confirmations": 7,
                "required_confirmations": 15,
                "block": 123,
            },
        ):
            response = self.client.post(
                "/api/wallet/bnb/empirical-smoke",
                json={"tx_hash": "0x" + "cd" * 32},
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()["status"], "WAITING_FOR_CONFIRMATIONS")
        self.assertEqual(response.get_json()["confirmations"], 7)

    def test_bnb_wallet_exposes_lossless_owner_empirical_intent(self):
        with patch("webapp.authenticated_uid", return_value="8789977826"), patch(
            "webapp.get_binding",
            return_value={"uid": "8789977826", "address": "0x1111111111111111111111111111111111111111"},
        ), patch(
            "webapp.authority_is_owner" if hasattr(webapp, "authority_is_owner") else "core.authority.is_owner",
            return_value=True,
        ), patch(
            "webapp.bnb_readiness",
            return_value={
                "effective_open": False,
                "ready": True,
                "chain_id": 56,
                "reasons": [],
            },
        ), patch(
            "webapp.bnb_settlement_allowed",
            return_value=True,
        ), patch(
            "webapp.get_bsc_config",
            return_value={"treasury_wallet": "0x2222222222222222222222222222222222222222"},
        ), patch(
            "webapp.state_manager.load_db",
            return_value={"bsc_settings": {}},
        ):
            response = self.client.get("/api/wallet/bnb")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["empirical_smoke"]["available"])
        self.assertEqual(data["empirical_smoke"]["amount_bnb"], "0.01")
        self.assertEqual(data["empirical_smoke"]["amount_wei"], "10000000000000000")
        self.assertEqual(data["empirical_smoke"]["chain_id"], 56)


if __name__ == "__main__":
    unittest.main()
