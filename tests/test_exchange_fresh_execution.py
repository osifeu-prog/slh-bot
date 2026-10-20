import copy
import unittest
from decimal import Decimal
from unittest.mock import patch

import webapp
from handlers.exchange_handler import ExchangeFreshCheckBlocked, _place


class ExchangeFreshExecutionTests(unittest.TestCase):
    def setUp(self):
        self.db = {
            "users": {
                "100": {
                    "academy": {"courses": {"algo_trading_999": {"stage": 7, "completed": [1, 2, 3, 4, 5, 6, 7]}}},
                    "wallet": {
                        "credits": 10.0,
                        "token_balance": 10.0,
                        "live_token_balance": 10.0,
                        "exchange_reserved_slh": 0.0,
                        "exchange_reserved_credits": 0.0,
                    }
                }
            },
            "exchange_orders": {},
            "exchange_trades": [],
            "exchange_requests": {},
            "exchange_sequence": 0,
            "trader_certifications": {"100": {"passed": True, "score": 10, "critical_pass": True, "quiz_version": "slh-trader-readiness-v1"}},
            "ledger": [],
        }
        self.load_db_patcher = patch(
            "webapp.state_manager.load_db", return_value=self.db
        )
        self.load_db_patcher.start()
        self.addCleanup(self.load_db_patcher.stop)
        self.live_proof_patcher = patch(
            "handlers.exchange_handler.require_fresh_live_exchange_proof",
            return_value={
            "status": "PASS",
            "checked_at": "2026-10-12T16:00:00+00:00",
            "railway_configured": "1",
            "public_gate": "OPEN",
            "public_verdict": "OPEN",
            "public_readiness": True,
            "public_updated_at": 1791830000.0,
        },
        )
        self.live_proof_patcher.start()
        self.addCleanup(self.live_proof_patcher.stop)

    @staticmethod
    def passed_check():
        return {
            "ok": True,
            "detail": "public state clean",
            "public_gate": "OPEN",
            "public_ready": True,
            "verdict": "OPEN",
            "execution_ready": True,
            "order_book_integrity": True,
            "trade_integrity": True,
            "money_invariants": True,
            "open_orders": 0,
        }

    @staticmethod
    def blocked_check():
        return {
            "ok": False,
            "detail": "money=EXCHANGE_NEGATIVE_BALANCE",
            "public_gate": "OPEN",
            "public_ready": False,
            "verdict": "BLOCKED",
            "execution_ready": False,
            "order_book_integrity": True,
            "trade_integrity": True,
            "money_invariants": False,
            "open_orders": 0,
        }

    def test_place_blocks_and_leaves_state_unchanged_when_fresh_check_fails(self):
        original = copy.deepcopy(self.db)
        with patch("handlers.exchange_handler.require_public_open"), patch(
            "core.system_checks.check_exchange_for_execution",
            return_value=self.blocked_check(),
        ) as fresh_check:
            with self.assertRaises(ExchangeFreshCheckBlocked) as raised:
                _place(
                    self.db,
                    "100",
                    "buy",
                    Decimal("1"),
                    Decimal("1"),
                    "fresh-check-blocked",
                )

        fresh_check.assert_called_once_with(self.db)
        self.assertEqual(self.db, original)
        self.assertEqual(str(raised.exception), "EXCHANGE_FRESH_CHECK_BLOCKED")
        self.assertEqual(raised.exception.check["verdict"], "BLOCKED")

    def test_place_returns_fresh_check_receipt_on_success(self):
        with patch("handlers.exchange_handler.require_public_open"), patch(
            "core.system_checks.check_exchange_for_execution",
            return_value=self.passed_check(),
        ) as fresh_check:
            result = _place(
                self.db,
                "100",
                "buy",
                Decimal("1"),
                Decimal("1"),
                "fresh-check-passed",
            )

        fresh_check.assert_called_once_with(self.db)
        self.assertEqual(result["status"], "open")
        self.assertEqual(result["trade_ids"], [])
        receipt = result["execution_check"]
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["verdict"], "OPEN")
        self.assertEqual(receipt["public_gate"], "OPEN")
        self.assertTrue(receipt["execution_ready"])
        self.assertTrue(receipt["order_book_integrity"])
        self.assertTrue(receipt["trade_integrity"])
        self.assertTrue(receipt["money_invariants"])
        self.assertTrue(receipt["checked_at"])
        self.assertEqual(self.db["users"]["100"]["wallet"]["exchange_reserved_credits"], 1.0)

    def test_rest_buy_sell_endpoint_returns_409_and_does_not_mutate_on_failed_check(self):
        original = copy.deepcopy(self.db)
        with patch("webapp.authenticated_uid", return_value="100"), patch(
            "webapp.state_manager.atomic_update",
            side_effect=lambda mutate: mutate(self.db),
        ), patch("handlers.exchange_handler.require_public_open"), patch(
            "core.system_checks.check_exchange_for_execution",
            return_value=self.blocked_check(),
        ) as fresh_check:
            response = webapp.app.test_client().post(
                "/api/v1/exchange/order",
                json={
                    "side": "buy",
                    "amount": "1",
                    "price": "1",
                    "client_request_id": "rest-fresh-check-blocked",
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "EXCHANGE_FRESH_CHECK_BLOCKED")
        self.assertEqual(response.get_json()["exchange_check"]["verdict"], "BLOCKED")
        self.assertEqual(self.db, original)
        fresh_check.assert_called_once_with(self.db)

    def test_rest_order_receipt_includes_fresh_execution_evidence(self):
        with patch("webapp.authenticated_uid", return_value="100"), patch(
            "webapp.state_manager.atomic_update",
            side_effect=lambda mutate: mutate(self.db),
        ), patch("handlers.exchange_handler.require_public_open"), patch(
            "core.system_checks.check_exchange_for_execution",
            return_value=self.passed_check(),
        ):
            response = webapp.app.test_client().post(
                "/api/v1/exchange/order",
                json={
                    "side": "sell",
                    "amount": "1",
                    "price": "1",
                    "client_request_id": "rest-fresh-check-passed",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        receipt = payload["execution_check"]
        self.assertEqual(receipt["status"], "PASS")
        self.assertTrue(receipt["checked_at"])
        self.assertTrue(receipt["execution_ready"])
        self.assertEqual(receipt["verdict"], "OPEN")
        self.assertEqual(payload["status"], "open")
        self.assertEqual(payload["trade_ids"], [])


    def test_closed_global_gate_is_reported_before_missing_trader_certification(self):
        from handlers.exchange_handler import execute_exchange_order

        blocked = ExchangeFreshCheckBlocked(
            {
                "status": "BLOCKED",
                "checked_at": "2026-10-20T11:00:00+00:00",
                "public_gate": "CLOSED",
                "verdict": "BLOCKED",
                "execution_ready": False,
                "detail": "public exchange gate is CLOSED",
            },
            checked_at="2026-10-20T11:00:00+00:00",
        )
        with patch(
            "handlers.exchange_handler.require_fresh_live_exchange_proof",
            side_effect=blocked,
        ), patch(
            "core.trader_certification.has_trader_certification",
            return_value=False,
        ) as certification_check:
            with self.assertRaises(ExchangeFreshCheckBlocked):
                execute_exchange_order(
                    uid="100", side="buy", amount=Decimal("1"),
                    price=Decimal("1"), request_id="global-gate-before-cert",
                )

        certification_check.assert_not_called()
        self.assertEqual(self.db["exchange_orders"], {})
        self.assertEqual(self.db["exchange_requests"], {})
        self.assertEqual(self.db["users"]["100"]["wallet"]["credits"], 10.0)



if __name__ == "__main__":
    unittest.main()
