import unittest
from unittest.mock import patch

import handlers.exchange_handler as exchange_handler
import handlers.webapp_data_handler as webapp_data_handler


class _Bot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))


class MiniAppExchangeExecutionReceiptTests(unittest.TestCase):
    def setUp(self):
        self.bot = _Bot()
        self.db = {"exchange_requests": {}}
        self.atomic_patch = patch.object(
            webapp_data_handler.state_manager,
            "atomic_update",
            side_effect=lambda mutate: mutate(self.db),
        )
        self.atomic_patch.start()
        self.addCleanup(self.atomic_patch.stop)

    def test_success_sends_full_fresh_canonical_execution_receipt(self):
        result = {
            "order_id": "O123",
            "filled": "2.00000000",
            "remaining": "0.00000000",
            "status": "filled",
            "trade_ids": ["T0000000042"],
            "execution_check": {
                "status": "PASS",
                "checked_at": "2026-10-12T16:00:00+00:00",
                "public_gate": "OPEN",
                "verdict": "OPEN",
                "execution_ready": True,
                "public_ready": True,
                "order_book_integrity": True,
                "trade_integrity": True,
                "money_invariants": True,
                "open_orders_before": 1,
                "live_runtime_check": "PASS",
                "live_checked_at": "2026-10-12T16:00:00+00:00",
                "live_railway_gate": "1",
                "live_public_gate": "OPEN",
                "live_public_verdict": "OPEN",
                "live_public_readiness": True,
                "live_public_updated_at": 1791830000.0,
            },
        }

        with patch.object(
            exchange_handler,
            "require_fresh_live_exchange_proof",
            return_value={
                "status": "PASS",
                "checked_at": "2026-10-12T16:00:00+00:00",
                "railway_configured": "1",
                "public_gate": "OPEN",
                "public_verdict": "OPEN",
                "public_readiness": True,
                "public_updated_at": 1791830000.0,
            },
        ), patch.object(exchange_handler, "_place", return_value=result):
            webapp_data_handler._exchange_order(
                self.bot, 123, "456", "buy_slh", "2", "1", "nonce-1"
            )

        self.assertEqual(len(self.bot.messages), 1)
        message = self.bot.messages[0][1]
        self.assertIn("Fresh canonical Exchange check: PASS", message)
        self.assertIn("Fresh live runtime confirmation: PASS", message)
        self.assertIn("Railway configured gate: 1", message)
        self.assertIn("execution_ready: PASS", message)
        self.assertIn("money_invariants: PASS", message)
        self.assertIn("T0000000042", message)

    def test_fresh_check_block_sends_explicit_blocked_receipt_without_success(self):
        check = {
            "public_gate": "CLOSED",
            "verdict": "BLOCKED",
            "execution_ready": False,
            "public_ready": True,
            "order_book_integrity": True,
            "trade_integrity": True,
            "money_invariants": True,
            "open_orders": 0,
            "detail": "public exchange gate is CLOSED",
        }
        blocked = exchange_handler.ExchangeFreshCheckBlocked(
            check, checked_at="2026-10-12T16:01:00+00:00"
        )

        with patch.object(
            exchange_handler,
            "require_fresh_live_exchange_proof",
            return_value={
                "status": "PASS",
                "checked_at": "2026-10-12T16:01:00+00:00",
                "railway_configured": "1",
                "public_gate": "OPEN",
                "public_verdict": "OPEN",
                "public_readiness": True,
                "public_updated_at": 1791830000.0,
            },
        ), patch.object(exchange_handler, "_place", side_effect=blocked):
            webapp_data_handler._exchange_order(
                self.bot, 123, "456", "sell_slh", "2", "1", "nonce-2"
            )

        self.assertEqual(len(self.bot.messages), 1)
        message = self.bot.messages[0][1]
        self.assertIn("Fresh canonical Exchange check: BLOCKED", message)
        self.assertIn("Reason: public exchange gate is CLOSED", message)
        self.assertIn("No order was placed or balances changed", message)
        self.assertNotIn("✅ BUY", message)
        self.assertNotIn("✅ SELL", message)
        self.assertNotIn("EXCHANGE_FRESH_CHECK_BLOCKED", message)

    def test_local_check_without_fresh_live_proof_is_not_a_green_receipt(self):
        receipt = exchange_handler.format_execution_receipt(
            "buy",
            {
                "order_id": "OLOCAL",
                "filled": "0.00000000",
                "remaining": "2.00000000",
                "trade_ids": [],
                "execution_check": {
                    "status": "PASS",
                    "checked_at": "2026-10-12T16:02:00+00:00",
                    "public_gate": "OPEN",
                    "verdict": "OPEN",
                    "execution_ready": True,
                    "public_ready": True,
                    "order_book_integrity": True,
                    "trade_integrity": True,
                    "money_invariants": True,
                },
            },
        )

        self.assertIn("Fresh canonical Exchange check: PASS", receipt)
        self.assertIn("Fresh live runtime confirmation: NOT VERIFIED", receipt)
        self.assertNotIn("✅ BUY", receipt)
        self.assertIn("Fresh live runtime gate proof is missing", receipt)

    def test_missing_legacy_execution_proof_is_not_presented_as_success(self):
        receipt = exchange_handler.format_execution_receipt(
            "buy",
            {
                "order_id": "OLEGACY",
                "filled": "0.00000000",
                "remaining": "2.00000000",
                "trade_ids": [],
            },
        )

        self.assertIn("Fresh canonical Exchange check: NOT VERIFIED", receipt)
        self.assertIn("Receipt does not prove a passing fresh execution check", receipt)
        self.assertNotIn("✅ BUY", receipt)


if __name__ == "__main__":
    unittest.main()
