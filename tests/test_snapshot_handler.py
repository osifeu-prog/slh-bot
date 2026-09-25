import os
import unittest
from unittest.mock import patch

from handlers.snapshot_handler import (
    _db_stats,
    _revenue_stats,
)


class SnapshotHandlerTests(unittest.TestCase):
    def test_db_stats_uses_canonical_keys(self):
        db = {
            "users": {"1": {"vip_access_until": 9999999999}},
            "ledger": [{"reason": "x"}],
            "stake_positions": {
                "a": {"status": "locked"},
                "b": {"status": "unlocked"},
            },
            "wallet_bindings": {"1": {"address": "0xabc"}},
            "ton_wallet_bindings": {"1": {"address": "EQ..."}},
            "star_item_orders": {"1": {"status": "FULFILLED"}},
            "vip_subscriptions": {"x": {"stars_paid": 499}},
        }
        stats = _db_stats(db)
        self.assertEqual(stats["users"], 1)
        self.assertEqual(stats["ledger"], 1)
        self.assertEqual(stats["stakes_total"], 2)
        self.assertEqual(stats["stakes_locked"], 1)
        self.assertEqual(stats["stakes_unlocked"], 1)
        self.assertEqual(stats["bnb_bindings"], 1)
        self.assertEqual(stats["ton_bindings"], 1)
        self.assertEqual(stats["star_orders"], 1)
        self.assertEqual(stats["vip_subscriptions"], 1)

    def test_revenue_stats_uses_canonical_external_xtr_rows(self):
        db = {
            "revenue_ledger": [
                {"currency": "XTR", "amount": 499, "reference": "c1", "uid": "1"},
                {"currency": "xtr", "amount": 299, "reference": "c2", "uid": "2"},
                {"currency": "XTR", "amount": 100, "reference": "", "uid": "3"},
                {"currency": "CREDITS", "amount": 999, "reference": "c3", "uid": "4"},
            ]
        }
        revenue = _revenue_stats(db)
        self.assertEqual(revenue["stars_total"], 798)
        self.assertEqual(revenue["customers"], 2)
        self.assertEqual(revenue["events"], 2)


if __name__ == "__main__":
    unittest.main()
