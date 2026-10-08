import unittest
from unittest.mock import patch

from core import exchange_housekeeping


class ExchangeHousekeepingTests(unittest.TestCase):
    def _db(self):
        return {
            "users": {
                "seller": {"wallet": {"token_balance": 10.0, "live_token_balance": 10.0, "exchange_reserved_slh": 0.0, "exchange_reserved_credits": 0.0, "credits": 0.0}},
                "buyer": {"wallet": {"token_balance": 0.0, "live_token_balance": 0.0, "exchange_reserved_slh": 0.0, "exchange_reserved_credits": 0.0, "credits": 100.0}},
            },
            "exchange_orders": {
                "O1": {
                    "id": "O1", "uid": "seller", "side": "sell",
                    "original_amount": "5.00000000", "remaining_amount": "0.00000000",
                    "limit_price": "2.00000000", "reserved_slh": "0.00000000",
                    "reserved_credits": "0.00000000", "sequence": 1,
                    "status": "filled", "created_at": "2026-10-08T00:00:00Z",
                },
                "O2": {
                    "id": "O2", "uid": "buyer", "side": "buy",
                    "original_amount": "5.00000000", "remaining_amount": "0.00000000",
                    "limit_price": "2.00000000", "reserved_slh": "0.00000000",
                    "reserved_credits": "0.00000000", "sequence": 2,
                    "status": "filled", "created_at": "2026-10-08T00:00:01Z",
                },
            },
            "exchange_trades": [
                {
                    "id": "T1", "buyer_uid": "buyer", "seller_uid": "seller",
                    "slh_amount": "5.00000000", "price": "2.00000000",
                    "credits_value": "10.00000000", "timestamp": "2026-10-08T00:00:02Z",
                    "buy_order_id": "O2", "sell_order_id": "O1",
                    "source": "test_seed",
                }
            ],
            "exchange_requests": {},
            "exchange_sequence": 2,
            "ledger": [],
            "slh_token_ledger": [],
        }

    def test_preview_classifies_seed_state(self):
        db = self._db()
        with patch("state_manager.load_db", return_value=db):
            result = exchange_housekeeping.preview()
        self.assertEqual(result["test_seed_trades"], 1)
        self.assertEqual(result["test_seed_orders"], 2)

    def test_archive_moves_seed_state_and_preserves_archive(self):
        db = self._db()
        with patch("state_manager.load_db", side_effect=[db, db]),              patch("state_manager.backup_db", return_value="state/backups/test.json"),              patch("state_manager.atomic_update", side_effect=lambda fn: fn(db)),              patch("core.audit.log_event", return_value=True):
            result = exchange_housekeeping.archive_test_state("owner")
        self.assertEqual(result["archived_trades"], 1)
        self.assertEqual(result["archived_orders"], 2)
        self.assertEqual(len(db["exchange_trades"]), 0)
        self.assertEqual(len(db["exchange_orders"]), 0)
        self.assertEqual(len(db["exchange_trade_archive"]), 1)
        self.assertEqual(len(db["exchange_order_archive"]), 2)

    def test_open_seed_order_is_never_archived(self):
        db = self._db()
        db["exchange_orders"]["O1"]["status"] = "open"
        db["exchange_orders"]["O1"]["remaining_amount"] = "5.00000000"
        db["exchange_orders"]["O1"]["reserved_slh"] = "5.00000000"
        with patch("state_manager.load_db", return_value=db):
            with self.assertRaisesRegex(ValueError, "EXCHANGE_TEST_ORDER_OPEN_CANNOT_ARCHIVE"):
                exchange_housekeeping.archive_test_state("owner")
        self.assertIn("O1", db["exchange_orders"])


if __name__ == "__main__":
    unittest.main()
