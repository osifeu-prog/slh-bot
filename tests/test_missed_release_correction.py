import unittest

from core.missed_release_correction import _plan


def _db(live=None):
    wallet = {"token_balance": 40000.0}
    if live is not ...:
        wallet["live_token_balance"] = live
    return {
        "users": {"100": {"wallet": wallet}},
        "exchange_orders": {
            "O9": {
                "id": "O9",
                "uid": "100",
                "side": "sell",
                "original_amount": "10000.00000000",
                "remaining_amount": "0.00000000",
                "reserved_slh": "0.00000000",
                "status": "cancelled",
            }
        },
        "exchange_trades": [],
        "ledger": [{
            "uid": "100",
            "before": 50000.0,
            "amount": -10000.0,
            "after": 40000.0,
            "reason": "exchange:sell_reserve",
            "meta": {"order_id": "O9"},
        }],
        "slh_token_ledger": [],
    }


class MissedReleaseCorrectionTests(unittest.TestCase):
    def test_legacy_wallet_is_eligible(self):
        plan = _plan(_db(), "O9")
        self.assertEqual(plan["wallet_model"], "legacy_internal")
        self.assertEqual(plan["restore"], "10000.00000000")
        self.assertEqual(plan["token_balance_before"], "40000.0")
        self.assertEqual(plan["token_balance_after"], "50000.00000000")

    def test_live_wallet_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "LIVE_BALANCE_PRESENT"):
            _plan(_db(live=40000.0), "O9")


if __name__ == "__main__":
    unittest.main()
