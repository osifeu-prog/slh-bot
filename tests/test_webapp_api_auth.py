import unittest
from unittest.mock import patch

import webapp


class WebAppApiAuthTests(unittest.TestCase):
    def setUp(self):
        self.client = webapp.app.test_client()

    def test_browser_quick_send_event_decoder_accepts_hexbytes_and_strings(self):
        from hexbytes import HexBytes
        from web3 import Web3

        sender = "0x468328B2a7C9b5629e87844Bb4531e7409400b34"
        event_topic = Web3.keccak(
            text="Transfer(address,address,uint256)"
        ).hex()
        sender_topic = "0x" + "0" * 24 + sender[2:].lower()
        raw_amount = "0x" + (10**15).to_bytes(32, "big").hex()

        self.assertEqual(
            webapp._normalize_hex_value(HexBytes(event_topic)),
            "0x" + event_topic,
        )
        self.assertEqual(
            webapp._normalize_hex_value(event_topic),
            "0x" + event_topic,
        )
        self.assertEqual(
            webapp._indexed_topic_address(HexBytes(sender_topic)).lower(),
            sender.lower(),
        )
        self.assertEqual(
            webapp._indexed_topic_address(sender_topic).lower(),
            sender.lower(),
        )
        self.assertEqual(
            int(webapp._normalize_hex_value(HexBytes(raw_amount)), 16),
            10**15,
        )

    def test_global_endpoints_require_telegram_auth(self):
        endpoints = (
            "/api/stats",
            "/api/leaderboard",
            "/api/v1/leaderboard",
            "/api/onchain/status",
        )
        with patch("webapp.authenticated_uid", return_value=None):
            for endpoint in endpoints:
                with self.subTest(endpoint=endpoint):
                    response = self.client.get(endpoint)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.get_json(), {"error": "TELEGRAM_AUTH_REQUIRED"})

    def test_stats_allows_authenticated_user(self):
        db = {
            "users": {"1": {"wallet": {"credits": 10}}},
            "agents": {"a": {}},
            "tasks": {"t": {}},
        }
        with patch("webapp.authenticated_uid", return_value="1"), patch(
            "webapp.load_db", return_value=db
        ):
            response = self.client.get("/api/stats")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "users": 1,
            "agents": 1,
            "tasks": 1,
            "credits": 10,
        })



    def test_wallet_handoff_allows_browser_send_target(self):
        token = "browser-send-token-1234567890"
        with patch("core.wallet_handoff.consume_handoff", return_value="8789977826"):
            response = self.client.get(
                "/wallet-handoff?code="+token+"&next=/slh-browser-send"
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/slh-browser-send")
        self.assertIn("slh_wallet_handoff=", response.headers.get("Set-Cookie", ""))
        self.assertIn("Path=/", response.headers.get("Set-Cookie", ""))

    def test_browser_quick_send_config_endpoint(self):
        cfg = {
            "ok": True,
            "preset": "owner_to_tzvika_1",
            "label": "צביקה",
            "sender_uid": "8789977826",
            "sender": "0x1111111111111111111111111111111111111111",
            "recipient_uid": "5010371391",
            "recipient": "0x2222222222222222222222222222222222222222",
            "amount_slh": "1",
            "chain_id": 56,
            "token_contract": "0x3333333333333333333333333333333333333333",
            "signing": "user_wallet_only",
            "custody": False,
        }
        with patch("webapp.authenticated_uid", return_value="8789977826"), patch(
            "core.slh_quick_send.get_quick_send_config", return_value=cfg
        ):
            response = self.client.get("/api/v1/wallet/slh/browser-quick-send")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), cfg)

    def test_wallet_handoff_repeated_get_uses_existing_session_cookie(self):
        token = "handoff-token-for-test-1234567890"
        with patch("core.wallet_handoff.consume_handoff") as consume, patch(
            "core.wallet_handoff.validate_session", return_value="5010371391"
        ):
            self.client.set_cookie("slh_wallet_handoff", token)
            response = self.client.get(
                "/wallet-handoff?code="+token+"&next=/slh-smoke"
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/slh-smoke")
        consume.assert_not_called()
        self.assertIn("slh_wallet_handoff=", response.headers.get("Set-Cookie", ""))
        self.assertIn("Path=/", response.headers.get("Set-Cookie", ""))

    def test_wallet_handoff_repeated_deeplink_without_cookie_reenters_valid_session(self):
        token = "handoff-token-for-test-1234567890"
        with patch(
            "core.wallet_handoff.consume_handoff",
            side_effect=ValueError("WALLET_HANDOFF_ALREADY_CONSUMED"),
        ) as consume, patch(
            "core.wallet_handoff.validate_session", return_value="5010371391"
        ):
            response = self.client.get(
                "/wallet-handoff?code="+token+"&next=/slh-smoke"
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/slh-smoke")
        consume.assert_called_once_with(token)

    def test_trezor_browser_send_page_supports_walletconnect(self):
        response = self.client.get("/slh-browser-send")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        for needle in (
            "Trezor Suite",
            "WalletConnect",
            "ethereum-provider@2.25.0",
            "/api/walletconnect/config",
            "eth_sendTransaction",
        ):
            self.assertIn(needle, body)
        self.assertIn("BSC · Chain 56", body)
        self.assertIn("1 SLH", body)

    def test_wallet_handoff_consumed_token_without_valid_session_is_rejected(self):
        token = "handoff-token-for-test-1234567890"
        with patch(
            "core.wallet_handoff.consume_handoff",
            side_effect=ValueError("WALLET_HANDOFF_ALREADY_CONSUMED"),
        ), patch(
            "core.wallet_handoff.validate_session", return_value=None
        ):
            response = self.client.get(
                "/wallet-handoff?code="+token+"&next=/slh-smoke"
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "WALLET_HANDOFF_INVALID"})

    def test_secondary_confirm_maps_transaction_not_found_to_retryable(self):
        with patch("webapp.authenticated_uid", return_value="5010371391"), patch(
            "core.secondary_distribution_service.confirm_secondary_slh_transfer",
            side_effect=ValueError("TRANSACTION_NOT_FOUND_RETRYABLE"),
        ):
            response = self.client.post(
                "/api/v1/distribution/secondary/confirm",
                json={"request_id": "r1", "tx_hash": "0xabc"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json(), {
            "error": "TRANSACTION_NOT_FOUND_RETRYABLE",
            "retryable": True,
        })


    def test_owner_quick_send_config_is_exposed(self):
        payload = {
            "ok": True,
            "preset": "owner_to_tzvika_1",
            "label": "צביקה",
            "sender_uid": "8789977826",
            "sender": "0x1111111111111111111111111111111111111111",
            "recipient_uid": "5010371391",
            "recipient": "0x2222222222222222222222222222222222222222",
            "amount_slh": "1",
            "chain_id": 56,
            "token_contract": "0xACb0A09414CEA1C879c67bB7A877E4e19480f022",
            "signing": "user_wallet_only",
            "custody": False,
        }
        with patch("webapp.authenticated_uid", return_value="8789977826"), patch(
            "core.slh_quick_send.get_quick_send_config", return_value=payload
        ):
            response = self.client.get("/api/v1/slh/quick-send/owner_to_tzvika_1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), payload)

    def test_quick_send_config_rejects_non_owner(self):
        with patch("webapp.authenticated_uid", return_value="5010371391"), patch(
            "core.slh_quick_send.get_quick_send_config",
            side_effect=PermissionError("OWNER_ONLY"),
        ):
            response = self.client.get("/api/v1/slh/quick-send/owner_to_tzvika_1")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json(), {"error": "OWNER_ONLY"})

    def test_tokenomics_exposes_unified_referral_read_model(self):
        db = {
            "users": {
                "1": {
                    "referral": {
                        "count": 3,
                        "referred_by": "9",
                    },
                    "gamification": {"points": 123},
                }
            },
            "commissions": {"1": 4.5},
        }
        referral = {
            "count": 3,
            "required": 5,
            "remaining": 2,
            "offer_open": True,
            "per_successful_referral": {"credits": 0.9, "points": 10},
        }
        with patch("webapp.authenticated_uid", return_value="1"), patch(
            "webapp.load_db", return_value=db
        ), patch(
            "core.profile_manager.get_user",
            return_value=db["users"]["1"],
        ), patch(
            "core.referral_reward.progress",
            return_value=referral,
        ), patch(
            "core.holiday_campaign.eligibility",
            return_value={"eligible": False, "reason": "CAMPAIGN_EXPIRED"},
        ), patch(
            "core.tokenomics.snapshot",
            return_value={"SLH": {"on_chain": True}},
        ), patch(
            "core.tokenomics.rewards_snapshot",
            return_value={"airdrop_slh": 0},
        ):
            response = self.client.get("/api/v1/tokenomics")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["user"]["points"], 123)
        self.assertEqual(payload["user"]["successful_referrals"], 3)
        self.assertEqual(payload["referral"]["count"], 3)
        self.assertEqual(payload["referral"]["required"], 5)
        self.assertEqual(payload["referral"]["remaining"], 2)
        self.assertEqual(payload["referral"]["commission_credits"], 4.5)
        self.assertEqual(payload["referral"]["commission_rate_on_credit_purchases"], 0.10)
        self.assertEqual(payload["referral"]["per_successful_referral"], {"credits": 0.9, "points": 10})
        self.assertEqual(payload["referral"]["referred_by"], "9")
        self.assertEqual(payload["referral"]["link"], "https://t.me/Me_ad_main_bot?start=ref_1")
        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["referral"]["commission_scope"], "Credits purchases only; Stars items/VIP are not referral-commissioned")


if __name__ == "__main__":
    unittest.main()
