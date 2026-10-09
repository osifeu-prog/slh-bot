import copy
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from core.system_checks import check_exchange_for_execution
from handlers import exchange_handler


class ExchangeSendTimeGateTests(unittest.TestCase):
    def _db(self):
        return {
            "users": {
                "seller": {
                    "wallet": {
                        "token_balance": 10.0,
                        "live_token_balance": 10.0,
                        "exchange_reserved_slh": 0.0,
                        "exchange_reserved_credits": 0.0,
                        "credits": 0.0,
                    }
                },
                "buyer": {
                    "wallet": {
                        "token_balance": 0.0,
                        "live_token_balance": 0.0,
                        "exchange_reserved_slh": 0.0,
                        "exchange_reserved_credits": 0.0,
                        "credits": 100.0,
                    }
                },
            },
            "transactions": [],
            "ledger": [],
            "slh_token_ledger": [],
            "exchange_orders": {},
            "exchange_trades": [],
            "exchange_requests": {},
            "exchange_sequence": 0,
        }

    def test_execution_check_requires_explicit_open_gate(self):
        db = self._db()
        with patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "0"}, clear=False):
            result = check_exchange_for_execution(db)
        self.assertFalse(result["ok"])
        self.assertEqual(result["public_gate"], "CLOSED")
        self.assertEqual(result["verdict"], "BLOCKED")

    def test_execution_check_accepts_a_valid_live_open_order(self):
        db = self._db()
        db["users"]["seller"]["wallet"]["exchange_reserved_slh"] = 2.0
        db["exchange_orders"]["O0000000001"] = {
            "id": "O0000000001",
            "uid": "seller",
            "side": "sell",
            "original_amount": "2.00000000",
            "remaining_amount": "2.00000000",
            "limit_price": "1.00000000",
            "reserved_slh": "2.00000000",
            "reserved_credits": "0.00000000",
            "sequence": 1,
            "status": "open",
            "client_request_id": "req-sell-1",
        }
        with patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "1"}, clear=False):
            result = check_exchange_for_execution(db)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["public_ready"])
        self.assertEqual(result["public_gate"], "OPEN")
        self.assertEqual(result["open_orders"], 1)

    def test_corrupt_live_reserve_blocks_order_entry_without_mutation(self):
        db = self._db()
        db["users"]["seller"]["wallet"]["exchange_reserved_slh"] = 3.0
        db["exchange_orders"]["O0000000001"] = {
            "id": "O0000000001",
            "uid": "seller",
            "side": "sell",
            "original_amount": "2.00000000",
            "remaining_amount": "2.00000000",
            "limit_price": "1.00000000",
            "reserved_slh": "2.00000000",
            "reserved_credits": "0.00000000",
            "sequence": 1,
            "status": "open",
            "client_request_id": "req-sell-1",
        }
        before = copy.deepcopy(db)
        with patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "1"}, clear=False):
            with self.assertRaisesRegex(ValueError, "EXCHANGE_FRESH_CHECK_BLOCKED"):
                exchange_handler._place(
                    db,
                    "buyer",
                    "buy",
                    exchange_handler._dec("1", "amount"),
                    exchange_handler._dec("1", "price"),
                    "req-buyer-1",
                )
        self.assertEqual(db, before)

    def test_order_response_contains_preflight_and_trade_receipt(self):
        db = self._db()
        with patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "1"}, clear=False):
            sell = exchange_handler._place(
                db, "seller", "sell",
                exchange_handler._dec("5", "amount"),
                exchange_handler._dec("2", "price"),
                "req-sell-2",
            )
            buy = exchange_handler._place(
                db, "buyer", "buy",
                exchange_handler._dec("5", "amount"),
                exchange_handler._dec("2", "price"),
                "req-buy-2",
            )
        self.assertEqual(sell["execution_check"]["status"], "PASS")
        self.assertEqual(buy["execution_check"]["status"], "PASS")
        self.assertEqual(buy["status"], "filled")
        self.assertEqual(len(buy["trade_ids"]), 1)
        self.assertEqual(buy["trade_ids"][0], db["exchange_trades"][-1]["id"])
        self.assertEqual(buy["order_id"], db["exchange_trades"][-1]["buy_order_id"])

    def test_move_quick_exchange_uses_authenticated_rest_flow(self):
        source = Path("mini_app.html").read_text(encoding="utf-8")
        start = source.index("function exTrade(side)")
        end = source.index("let __secondaryPrepared", start)
        function = source[start:end]
        self.assertIn("sendExchangeOrder(side, a, pr)", function)
        self.assertNotIn("openAction(", function)


if __name__ == "__main__":
    unittest.main()
