import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import webapp


class WebAppExchangeOrderIntentTests(unittest.TestCase):
    def setUp(self):
        self.client = webapp.app.test_client()
        self.db = {
            "users": {
                "buyer": {
                    "wallet": {
                        "credits": 100.0,
                        "token_balance": 0.0,
                        "live_token_balance": 0.0,
                        "exchange_reserved_slh": 0.0,
                        "exchange_reserved_credits": 0.0,
                    }
                },
                "seller": {
                    "wallet": {
                        "credits": 0.0,
                        "token_balance": 10.0,
                        "live_token_balance": 10.0,
                        "exchange_reserved_slh": 0.0,
                        "exchange_reserved_credits": 0.0,
                    }
                },
            },
            "exchange_orders": {},
            "exchange_trades": [],
            "exchange_requests": {},
            "exchange_sequence": 0,
            "ledger": [],
            "slh_token_ledger": [],
        }
        from handlers import exchange_handler

        self.original_uid = webapp.authenticated_uid
        self.original_load_db = webapp.state_manager.load_db
        self.original_atomic_update = webapp.state_manager.atomic_update
        self.live_proof_patch = patch.object(
            exchange_handler,
            "require_fresh_live_exchange_proof",
            return_value={
            "status": "PASS",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "railway_configured": "1",
            "public_gate": "OPEN",
            "public_verdict": "OPEN",
            "public_readiness": True,
            "public_updated_at": datetime.now(timezone.utc).timestamp(),
        },
        )
        self.live_proof_mock = self.live_proof_patch.start()
        self.addCleanup(self.live_proof_patch.stop)
        webapp.authenticated_uid = lambda: "buyer"
        webapp.state_manager.load_db = lambda: self.db
        webapp.state_manager.atomic_update = lambda mutate: mutate(self.db)

    def tearDown(self):
        webapp.authenticated_uid = self.original_uid
        webapp.state_manager.load_db = self.original_load_db
        webapp.state_manager.atomic_update = self.original_atomic_update

    @staticmethod
    def passing_check():
        return {
            "ok": True,
            "verdict": "OPEN",
            "public_gate": "OPEN",
            "public_ready": True,
            "execution_ready": True,
            "order_book_integrity": True,
            "trade_integrity": True,
            "money_invariants": True,
            "open_orders": 0,
            "detail": "public state clean",
        }

    def submit(self, *, side="buy", amount="2", price="3", request_id="req-1"):
        return self.client.post(
            "/api/v1/exchange/order",
            json={
                "side": side,
                "amount": amount,
                "price": price,
                "client_request_id": request_id,
            },
        )

    def test_fresh_canonical_check_runs_in_order_submission_and_receipt(self):
        with patch(
            "core.system_checks.check_exchange_for_execution",
            return_value=self.passing_check(),
        ) as fresh_check:
            response = self.submit()

        self.assertEqual(response.status_code, 200)
        fresh_check.assert_called_once_with(self.db)
        payload = response.get_json()
        self.assertEqual(payload["status"], "open")
        self.assertEqual(payload["execution_check"]["status"], "PASS")
        self.assertEqual(payload["execution_check"]["public_gate"], "OPEN")
        self.assertTrue(payload["execution_check"]["execution_ready"])
        self.assertTrue(payload["execution_check"]["money_invariants"])
        self.assertTrue(payload["execution_check"]["checked_at"])
        self.live_proof_mock.assert_called_once_with()
        execution_check = payload["execution_check"]
        self.assertEqual(execution_check["live_runtime_check"], "PASS")
        self.assertEqual(execution_check["live_railway_gate"], "1")
        self.assertEqual(execution_check["live_public_gate"], "OPEN")
        self.assertEqual(execution_check["live_public_verdict"], "OPEN")
        self.assertIs(execution_check["live_public_readiness"], True)
        self.assertIsInstance(execution_check["live_public_updated_at"], (int, float))
        checked_at = datetime.fromisoformat(execution_check["checked_at"].replace("Z", "+00:00"))
        live_checked_at = datetime.fromisoformat(execution_check["live_checked_at"].replace("Z", "+00:00"))
        self.assertLessEqual(abs((checked_at - live_checked_at).total_seconds()), 30)
        self.assertEqual(len(self.db["exchange_orders"]), 1)

    def test_failed_fresh_check_blocks_without_creating_order_or_debiting_wallet(self):
        blocked = {
            **self.passing_check(),
            "ok": False,
            "verdict": "BLOCKED",
            "public_gate": "CLOSED",
            "public_ready": False,
            "execution_ready": False,
            "detail": "public exchange gate is CLOSED",
        }
        before_credits = self.db["users"]["buyer"]["wallet"]["credits"]

        with patch(
            "core.system_checks.check_exchange_for_execution",
            return_value=blocked,
        ):
            response = self.submit()

        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertEqual(payload["code"], "EXCHANGE_FRESH_CHECK_BLOCKED")
        self.assertEqual(payload["exchange_check"]["public_gate"], "CLOSED")
        self.live_proof_mock.assert_called_once_with()
        self.assertEqual(payload["exchange_check"]["live_runtime_check"], "PASS")
        self.assertEqual(self.db["exchange_orders"], {})
        self.assertEqual(
            self.db["users"]["buyer"]["wallet"]["credits"],
            before_credits,
        )
        self.assertEqual(
            self.db["users"]["buyer"]["wallet"]["exchange_reserved_credits"],
            0.0,
        )

    def test_unavailable_live_proof_blocks_before_local_check_or_money_mutation(self):
        from handlers import exchange_handler
        from handlers.exchange_handler import ExchangeFreshCheckBlocked

        before_credits = self.db["users"]["buyer"]["wallet"]["credits"]
        checked_at = datetime.now(timezone.utc).isoformat()
        blocked = ExchangeFreshCheckBlocked({
            "checked_at": checked_at,
            "public_gate": "UNKNOWN",
            "verdict": "BLOCKED",
            "public_ready": False,
            "execution_ready": False,
            "order_book_integrity": False,
            "trade_integrity": False,
            "money_invariants": False,
            "detail": "public runtime probe failed",
            "railway_configured": "1",
            "live_runtime_check": "BLOCKED",
            "live_checked_at": checked_at,
            "live_public_gate": "UNKNOWN",
        })

        with patch.object(
            exchange_handler,
            "require_fresh_live_exchange_proof",
            side_effect=blocked,
        ) as live_check, patch(
            "core.system_checks.check_exchange_for_execution"
        ) as local_check:
            response = self.submit(request_id="live-proof-unavailable")

        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertEqual(payload["code"], "EXCHANGE_FRESH_CHECK_BLOCKED")
        self.assertEqual(payload["exchange_check"]["live_runtime_check"], "BLOCKED")
        live_check.assert_called_once_with()
        local_check.assert_not_called()
        self.assertEqual(self.db["exchange_orders"], {})
        self.assertEqual(self.db["exchange_trades"], [])
        self.assertEqual(self.db["exchange_requests"], {})
        self.assertEqual(self.db["users"]["buyer"]["wallet"]["credits"], before_credits)
        self.assertEqual(
            self.db["users"]["buyer"]["wallet"]["exchange_reserved_credits"],
            0.0,
        )

    def test_reused_request_id_with_different_order_intent_is_rejected(self):
        with patch(
            "core.system_checks.check_exchange_for_execution",
            return_value=self.passing_check(),
        ):
            first = self.submit(
                side="buy", amount="2", price="3", request_id="same-request"
            )
            second = self.submit(
                side="sell", amount="1", price="2", request_id="same-request"
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(
            second.get_json()["code"],
            "EXCHANGE_IDEMPOTENCY_KEY_REUSED",
        )
        self.assertEqual(len(self.db["exchange_orders"]), 1)
        only_order = next(iter(self.db["exchange_orders"].values()))
        self.assertEqual(only_order["side"], "buy")
        self.assertEqual(only_order["original_amount"], "2.00000000")
        self.assertEqual(only_order["limit_price"], "3.00000000")
        self.assertEqual(
            self.db["users"]["buyer"]["wallet"]["credits"],
            94.0,
        )


    def test_idempotent_retry_is_marked_as_replay_without_second_execution(self):
        request_id = "retry-after-network"
        key = f"WEBAPP-EXCHANGE-buyer-{request_id}"
        with patch(
            "core.system_checks.check_exchange_for_execution",
            return_value=self.passing_check(),
        ) as fresh_check:
            first = self.submit(request_id=request_id)
            stored_receipt_before_retry = dict(self.db["exchange_requests"][key])
            credits_after_first = self.db["users"]["buyer"]["wallet"]["credits"]
            sequence_after_first = self.db["exchange_sequence"]
            second = self.submit(request_id=request_id)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        first_payload = first.get_json()
        second_payload = second.get_json()
        self.assertIs(first_payload.get("idempotent_replay"), False)
        self.assertIs(second_payload.get("idempotent_replay"), True)
        self.assertEqual(first_payload["order_id"], second_payload["order_id"])
        self.assertEqual(self.db["exchange_requests"][key], stored_receipt_before_retry)
        self.assertEqual(len(self.db["exchange_orders"]), 1)
        self.assertEqual(self.db["exchange_sequence"], sequence_after_first)
        self.assertEqual(
            self.db["users"]["buyer"]["wallet"]["credits"],
            credits_after_first,
        )
        fresh_check.assert_called_once_with(self.db)


    def test_frozen_account_cannot_submit_buy_or_sell_without_side_effects(self):
        buyer = self.db["users"]["buyer"]
        buyer["frozen"] = True
        buyer["wallet"]["token_balance"] = 10.0
        buyer["wallet"]["live_token_balance"] = 10.0
        wallet_before = dict(buyer["wallet"])
        ledger_before = list(self.db["ledger"])

        with patch(
            "core.system_checks.check_exchange_for_execution",
            return_value=self.passing_check(),
        ) as fresh_check:
            for side in ("buy", "sell"):
                response = self.submit(
                    side=side, amount="1", price="1", request_id=f"frozen-{side}"
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error"], "ACCOUNT_FROZEN")

        fresh_check.assert_not_called()
        self.assertEqual(self.db["exchange_orders"], {})
        self.assertEqual(self.db["exchange_trades"], [])
        self.assertEqual(self.db["exchange_requests"], {})
        self.assertEqual(buyer["wallet"], wallet_before)
        self.assertEqual(self.db["ledger"], ledger_before)

    def test_frozen_resting_order_is_not_matched(self):
        from handlers.exchange_handler import _match

        frozen_sell = {
            "id": "O-FROZEN", "uid": "seller", "side": "sell",
            "original_amount": "1.00000000",
            "remaining_amount": "1.00000000",
            "limit_price": "1.00000000",
            "reserved_slh": "1.00000000",
            "reserved_credits": "0.00000000",
            "sequence": 1, "status": "open",
        }
        incoming_buy = {
            "id": "O-BUY", "uid": "buyer", "side": "buy",
            "original_amount": "1.00000000",
            "remaining_amount": "1.00000000",
            "limit_price": "1.00000000",
            "reserved_slh": "0.00000000",
            "reserved_credits": "1.00000000",
            "sequence": 2, "status": "open",
        }
        db = {
            "users": {
                "buyer": {"wallet": {
                    "credits": 0.0, "token_balance": 0.0,
                    "live_token_balance": 0.0, "exchange_reserved_slh": 0.0,
                    "exchange_reserved_credits": 1.0,
                }},
                "seller": {"frozen": True, "wallet": {
                    "credits": 0.0, "token_balance": 1.0,
                    "live_token_balance": 1.0, "exchange_reserved_slh": 1.0,
                    "exchange_reserved_credits": 0.0,
                }},
            },
            "exchange_orders": {"O-FROZEN": frozen_sell, "O-BUY": incoming_buy},
            "exchange_trades": [],
            "exchange_sequence": 2,
            "ledger": [],
            "slh_token_ledger": [],
        }

        filled, remaining = _match(db, incoming_buy)

        self.assertEqual(filled, 0)
        self.assertEqual(remaining, 1)
        self.assertEqual(db["exchange_trades"], [])
        self.assertEqual(frozen_sell["status"], "open")
        self.assertEqual(incoming_buy["status"], "open")


if __name__ == "__main__":
    unittest.main()
