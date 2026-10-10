import os
import unittest
from unittest.mock import patch

from handlers import exchange_handler
from core.exchange_gate import public_open


class ExchangePublicGateTests(unittest.TestCase):
    def _db(self):
        return {
            "users": {
                "seller": {"wallet": {"token_balance": 10.0, "live_token_balance": 10.0, "exchange_reserved_slh": 0.0, "exchange_reserved_credits": 0.0, "credits": 0.0}},
                "buyer": {"wallet": {"token_balance": 0.0, "live_token_balance": 0.0, "exchange_reserved_slh": 0.0, "exchange_reserved_credits": 0.0, "credits": 100.0}},
            },
            "ledger": [],
            "slh_token_ledger": [],
            "exchange_orders": {},
            "exchange_trades": [],
            "exchange_requests": {},
            "exchange_sequence": 0,
        }

    def test_order_entry_is_fail_closed(self):
        db = self._db()
        with patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "0"}, clear=False):
            self.assertFalse(public_open())
            with self.assertRaises(exchange_handler.ExchangeFreshCheckBlocked) as blocked:
                exchange_handler._place(
                    db, "seller", "sell",
                    exchange_handler._dec("1", "amount"),
                    exchange_handler._dec("2", "price"),
                    "test-closed",
                )
            self.assertEqual(blocked.exception.check["status"], "BLOCKED")
            self.assertEqual(blocked.exception.check["public_gate"], "CLOSED")
            self.assertFalse(blocked.exception.check["execution_ready"])
            self.assertTrue(blocked.exception.check["checked_at"])
        self.assertEqual(db["exchange_orders"], {})
        self.assertEqual(db["slh_token_ledger"], [])

    def test_open_gate_allows_internal_match(self):
        db = self._db()
        with patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "1"}, clear=False):
            sell = exchange_handler._place(
                db, "seller", "sell",
                exchange_handler._dec("5", "amount"),
                exchange_handler._dec("2", "price"),
                "req-open-sell",
            )
            buy = exchange_handler._place(
                db, "buyer", "buy",
                exchange_handler._dec("5", "amount"),
                exchange_handler._dec("2", "price"),
                "req-open-buy",
            )
        self.assertEqual(sell["status"], "open")
        self.assertEqual(buy["status"], "filled")
        self.assertEqual(len(db["exchange_trades"]), 1)
        self.assertEqual(db["users"]["buyer"]["wallet"]["token_balance"], 5.0)
        self.assertEqual(db["users"]["seller"]["wallet"]["credits"], 10.0)

    def test_clean_state_is_ready_to_open(self):
        from core import system_checks

        db = self._db()
        with patch("state_manager.load_db", return_value=db), patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "0"}, clear=False):
            result = system_checks.check_exchange()
        self.assertTrue(result["public_ready"])
        self.assertEqual(result["public_gate"], "CLOSED")
        self.assertEqual(result["verdict"], "READY_TO_OPEN")


if __name__ == "__main__":
    unittest.main()
