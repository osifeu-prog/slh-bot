import os
import unittest
from unittest.mock import patch

from handlers import exchange_handler
from core.exchange_gate import public_open


class ExchangePublicGateTests(unittest.TestCase):
    def _db(self):
        return {
            "users": {
                "seller": {
                    "academy": {"courses": {"algo_trading_999": {"stage": 7, "completed": [1, 2, 3, 4, 5, 6, 7]}}},
                    "wallet": {"token_balance": 10.0, "live_token_balance": 10.0, "exchange_reserved_slh": 0.0, "exchange_reserved_credits": 0.0, "credits": 0.0},
                },
                "buyer": {
                    "academy": {"courses": {"algo_trading_999": {"stage": 7, "completed": [1, 2, 3, 4, 5, 6, 7]}}},
                    "wallet": {"token_balance": 0.0, "live_token_balance": 0.0, "exchange_reserved_slh": 0.0, "exchange_reserved_credits": 0.0, "credits": 100.0},
                },
                "8789977826": {
                    "wallet": {"credits": 0.0},
                },
            },
            "ledger": [{
                "uid": "8789977826",
                "before": 0.0,
                "amount": 0.0,
                "after": 0.0,
                "reason": "test:credits_anchor",
                "meta": {"ledger_domain": "credits"},
            }, {
                "time": "2026-09-18T11:57:23+00:00",
                "uid": "buyer", "before": 1.0, "amount": -1.0, "after": 0.0,
                "reason": "exchange:sell_reserve", "meta": {"order_id": "O_LEGACY"},
            }, {
                "time": "2026-09-18T11:58:23+00:00",
                "uid": "buyer", "before": 0.0, "amount": 1.0, "after": 1.0,
                "reason": "exchange:cancel_release", "meta": {"order_id": "O_LEGACY"},
            }],
            "slh_token_ledger": [],
            "exchange_orders": {
                "O_LEGACY": {
                    "id": "O_LEGACY", "uid": "buyer", "side": "sell",
                    "original_amount": "1.00000000", "remaining_amount": "0.00000000",
                    "limit_price": "1.00000000", "reserved_slh": "0.00000000",
                    "reserved_credits": "0.00000000", "sequence": 1, "status": "cancelled",
                }
            },
            "exchange_trades": [],
            "exchange_requests": {},
            "exchange_sequence": 1,
            "trader_certifications": {
                "seller": {"passed": True, "score": 10, "critical_pass": True, "quiz_version": "slh-trader-readiness-v1"},
                "buyer": {"passed": True, "score": 10, "critical_pass": True, "quiz_version": "slh-trader-readiness-v1"},
            },
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
        self.assertEqual(set(db["exchange_orders"]), {"O_LEGACY"})
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

    def test_balanced_legacy_reserve_history_is_ready_to_open(self):
        from core import system_checks

        db = self._db()
        with patch("state_manager.load_db", return_value=db), patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "0"}, clear=False):
            result = system_checks.check_exchange()
        self.assertTrue(result["public_ready"])
        self.assertEqual(result["public_gate"], "CLOSED")
        self.assertEqual(result["verdict"], "READY_TO_OPEN")



    def test_public_readiness_blocks_when_owner_credits_audit_is_blocked(self):
        from core import system_checks

        db = self._db()
        blocked_audit = {
            "status": "BLOCKED",
            "blockers": ["ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY"],
            "finding_count": 1,
            "findings": [{"type": "SEQUENCE_GAP_REQUIRES_SOURCE_EVIDENCE"}],
        }
        with patch("state_manager.load_db", return_value=db), patch(
            "core.account_ledger_audit.audit_account_ledger",
            return_value=blocked_audit,
        ), patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "0"}, clear=False):
            result = system_checks.check_exchange()

        self.assertTrue(result["order_book_integrity"])
        self.assertTrue(result["trade_integrity"])
        self.assertTrue(result["money_invariants"])
        self.assertFalse(result["account_ledger_integrity"])
        self.assertEqual(result["account_ledger_status"], "BLOCKED")
        self.assertFalse(result["public_ready"])
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn("account_ledger=BLOCKED", result["detail"])

    def test_valid_trade_parties_pass_exchange_readiness(self):
        from core import system_checks

        db = self._matched_trade_db()
        with patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "0"}, clear=False):
            result = system_checks.check_exchange(db)

        self.assertTrue(result["trade_integrity"])
        self.assertTrue(result["public_ready"])
        self.assertEqual(result["verdict"], "READY_TO_OPEN")

    def test_mismatched_buyer_order_owner_blocks_exchange_readiness(self):
        from core import system_checks

        db = self._matched_trade_db()
        trade = db["exchange_trades"][0]
        trade["buyer_uid"] = "buyer-identity-mismatch"

        with patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "0"}, clear=False):
            result = system_checks.check_exchange(db)

        self.assertFalse(result["trade_integrity"])
        self.assertFalse(result["public_ready"])
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn(f"trade:{trade['id']}:buyer_order_owner_mismatch", result["detail"])

    def test_mismatched_seller_order_owner_blocks_exchange_readiness(self):
        from core import system_checks

        db = self._matched_trade_db()
        trade = db["exchange_trades"][0]
        trade["seller_uid"] = "seller-identity-mismatch"

        with patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "0"}, clear=False):
            result = system_checks.check_exchange(db)

        self.assertFalse(result["trade_integrity"])
        self.assertFalse(result["public_ready"])
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn(f"trade:{trade['id']}:seller_order_owner_mismatch", result["detail"])


    def test_execution_check_blocks_mismatched_buyer_order_owner(self):
        from core.system_checks import check_exchange_for_execution

        db = self._matched_trade_db()
        trade = db["exchange_trades"][0]
        trade["buyer_uid"] = "buyer-identity-mismatch"

        with patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "1"}, clear=False):
            result = check_exchange_for_execution(db)

        self.assertFalse(result["trade_integrity"])
        self.assertFalse(result["execution_ready"])
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn(f"trade:{trade['id']}:buyer_order_owner_mismatch", result["detail"])

    def test_execution_check_blocks_mismatched_seller_order_owner(self):
        from core.system_checks import check_exchange_for_execution

        db = self._matched_trade_db()
        trade = db["exchange_trades"][0]
        trade["seller_uid"] = "seller-identity-mismatch"

        with patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "1"}, clear=False):
            result = check_exchange_for_execution(db)

        self.assertFalse(result["trade_integrity"])
        self.assertFalse(result["execution_ready"])
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn(f"trade:{trade['id']}:seller_order_owner_mismatch", result["detail"])

    def test_execution_check_allows_party_consistent_trade_when_gate_is_open(self):
        from core.system_checks import check_exchange_for_execution

        db = self._matched_trade_db()

        with patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "1"}, clear=False):
            result = check_exchange_for_execution(db)

        self.assertTrue(result["trade_integrity"])
        self.assertTrue(result["execution_ready"])
        self.assertEqual(result["verdict"], "OPEN")


    def test_wrong_side_for_linked_buy_order_blocks_readiness(self):
        from core.system_checks import check_exchange

        db = self._matched_trade_db()
        trade = db["exchange_trades"][0]
        db["exchange_orders"][str(trade["buy_order_id"])]["side"] = "sell"

        with patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "0"}, clear=False):
            result = check_exchange(db)

        self.assertFalse(result["trade_integrity"])
        self.assertFalse(result["public_ready"])
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn(f"trade:{trade['id']}:bad_buy_order", result["detail"])

    def test_missing_linked_buy_order_blocks_readiness(self):
        from core.system_checks import check_exchange

        db = self._matched_trade_db()
        trade = db["exchange_trades"][0]
        trade["buy_order_id"] = "O_MISSING"

        with patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "0"}, clear=False):
            result = check_exchange(db)

        self.assertFalse(result["trade_integrity"])
        self.assertFalse(result["public_ready"])
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn(f"trade:{trade['id']}:bad_buy_order", result["detail"])

    def test_wrong_credits_value_blocks_readiness(self):
        from core.system_checks import check_exchange

        db = self._matched_trade_db()
        trade = db["exchange_trades"][0]
        trade["credits_value"] = "999.00000000"

        with patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "0"}, clear=False):
            result = check_exchange(db)

        self.assertFalse(result["trade_integrity"])
        self.assertFalse(result["public_ready"])
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn(f"trade:{trade['id']}:bad_value", result["detail"])

    def test_duplicate_trade_id_blocks_readiness(self):
        from core.system_checks import check_exchange

        db = self._matched_trade_db()
        trade = db["exchange_trades"][0]
        db["exchange_trades"].append(dict(trade))

        with patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "0"}, clear=False):
            result = check_exchange(db)

        self.assertFalse(result["trade_integrity"])
        self.assertFalse(result["public_ready"])
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn(f"trade:{trade['id']}:duplicate_or_missing_id", result["detail"])

    def test_execution_check_blocks_trade_price_above_buy_limit(self):
        from core.system_checks import check_exchange_for_execution

        db = self._matched_trade_db()
        trade = db["exchange_trades"][0]
        trade["price"] = "3.00000000"
        trade["credits_value"] = "15.00000000"

        with patch.dict(os.environ, {"SLH_EXCHANGE_PUBLIC_OPEN": "1"}, clear=False):
            result = check_exchange_for_execution(db)

        self.assertFalse(result["trade_integrity"])
        self.assertFalse(result["execution_ready"])
        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn(f"trade:{trade['id']}:price_above_buy_limit", result["detail"])


if __name__ == "__main__":
    unittest.main()
