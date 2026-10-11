import unittest
from datetime import datetime
from unittest.mock import patch

from core import exchange_read_model as target


def _valid_db():
    return {
        "users": {"42": {"wallet": {"credits": 100, "token_balance": 10}}},
        "exchange_orders": {},
        "exchange_trades": [],
        "exchange_requests": {},
        "exchange_sequence": 0,
    }


def _check(opened):
    return {
        "ok": opened,
        "execution_ready": opened,
        "public_gate": "OPEN" if opened else "CLOSED",
        "verdict": "OPEN" if opened else "BLOCKED",
        "public_ready": opened,
        "order_book_integrity": opened,
        "trade_integrity": opened,
        "money_invariants": opened,
        "detail": "public state clean" if opened else "public exchange gate is CLOSED",
        "open_orders": 0,
        "test_seed_open": 0,
        "recent_trades": 0,
        "test_seed_trades": 0,
    }


class ExchangeReadModelGateTruthTests(unittest.TestCase):
    def test_closed_canonical_gate_never_appears_open_even_with_market_data(self):
        db = _valid_db()
        db["exchange_orders"] = {
            "O1": {
                "id": "O1",
                "uid": "42",
                "side": "buy",
                "status": "open",
                "remaining_amount": "1.00000000",
                "limit_price": "1.00000000",
                "sequence": 1,
            }
        }
        db["exchange_trades"] = [{
            "id": "T1",
            "buyer_uid": "42",
            "seller_uid": "43",
            "slh_amount": "1.00000000",
            "price": "1.00000000",
            "credits_value": "1.00000000",
        }]

        with patch.object(target, "_load_db", return_value=db), patch(
            "core.system_checks.check_exchange_for_execution",
            return_value=_check(False),
        ) as canonical_check:
            summary = target.get_exchange_summary()

        canonical_check.assert_called_once_with(db)
        self.assertFalse(summary["status"]["open"])
        self.assertEqual(summary["status"]["public_gate"], "CLOSED")
        self.assertEqual(summary["status"]["verdict"], "BLOCKED")
        self.assertFalse(summary["status"]["execution_ready"])
        self.assertEqual(summary["status"]["total_orders"], 1)
        self.assertEqual(summary["status"]["total_trades"], 1)
        self.assertTrue(summary["status"]["checked_at"])

    def test_green_status_requires_every_canonical_execution_invariant(self):
        db = _valid_db()
        with patch.object(target, "_load_db", return_value=db), patch(
            "core.system_checks.check_exchange_for_execution",
            return_value=_check(True),
        ) as canonical_check:
            summary = target.get_exchange_summary()

        canonical_check.assert_called_once_with(db)
        status = summary["status"]
        self.assertTrue(status["open"])
        self.assertEqual(status["public_gate"], "OPEN")
        self.assertEqual(status["verdict"], "OPEN")
        self.assertTrue(status["execution_ready"])
        self.assertTrue(status["public_ready"])
        self.assertTrue(status["order_book_integrity"])
        self.assertTrue(status["trade_integrity"])
        self.assertTrue(status["money_invariants"])
        self.assertIsInstance(datetime.fromisoformat(status["checked_at"]), datetime)

    def test_missing_canonical_state_fails_closed_without_checking_empty_db(self):
        with patch.object(target, "_load_db", return_value=None), patch(
            "core.system_checks.check_exchange_for_execution"
        ) as canonical_check:
            summary = target.get_exchange_summary()

        canonical_check.assert_not_called()
        self.assertFalse(summary["status"]["open"])
        self.assertEqual(summary["status"]["public_gate"], "CLOSED")
        self.assertEqual(summary["status"]["verdict"], "BLOCKED")
        self.assertFalse(summary["status"]["execution_ready"])
        self.assertIn("unreadable", summary["status"]["detail"].lower())

    def test_missing_optional_exchange_requests_key_uses_canonical_checker(self):
        db = _valid_db()
        db.pop("exchange_requests", None)
        with patch.object(target, "_load_db", return_value=db), patch(
            "core.system_checks.check_exchange_for_execution",
            return_value=_check(True),
        ) as canonical_check:
            summary = target.get_exchange_summary()

        canonical_check.assert_called_once_with(db)
        self.assertTrue(summary["status"]["open"])

    def test_invalid_canonical_exchange_shapes_fail_closed(self):
        db = _valid_db()
        db["exchange_orders"] = []
        with patch.object(target, "_load_db", return_value=db), patch(
            "core.system_checks.check_exchange_for_execution"
        ) as canonical_check:
            summary = target.get_exchange_summary()

        canonical_check.assert_not_called()
        self.assertFalse(summary["status"]["open"])
        self.assertEqual(summary["status"]["public_gate"], "CLOSED")
        self.assertFalse(summary["status"]["order_book_integrity"])


if __name__ == "__main__":
    unittest.main()
