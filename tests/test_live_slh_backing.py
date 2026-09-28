import unittest

from core import slh_distribution


class LiveSlhBackingTests(unittest.TestCase):
    def db(self):
        return {
            "users": {
                "seller": {"wallet": {"token_balance": 100.0, "live_token_balance": 0.0}},
                "buyer": {"wallet": {"token_balance": 0.0, "live_token_balance": 0.0}},
            },
            "slh_token_ledger": [],
        }

    def test_unbacked_balance_cannot_enter_exchange_reserve(self):
        db = self.db()
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_LIVE_SLH"):
            slh_distribution.reserve_in_db(
                db, uid="seller", amount=10,
                event_id="reserve-1", order_id="O1",
            )

    def test_backed_balance_reserves_without_changing_total_supply(self):
        db = self.db()
        db["users"]["seller"]["wallet"]["token_balance"] = 100.0
        db["users"]["seller"]["wallet"]["live_token_balance"] = 100.0

        result = slh_distribution.reserve_in_db(
            db, uid="seller", amount=40,
            event_id="reserve-1", order_id="O1",
        )
        self.assertEqual(result["status"], "completed")
        wallet = db["users"]["seller"]["wallet"]
        self.assertEqual(wallet["token_balance"], 100.0)
        self.assertEqual(wallet["live_token_balance"], 100.0)
        self.assertEqual(wallet["exchange_reserved_slh"], 40.0)

    def test_settlement_transfers_only_backed_supply(self):
        db = self.db()
        db["users"]["seller"]["wallet"]["token_balance"] = 100.0
        db["users"]["seller"]["wallet"]["live_token_balance"] = 40.0
        db["users"]["seller"]["wallet"]["exchange_reserved_slh"] = 40.0

        result = slh_distribution.settle_reserve_in_db(
            db, seller_uid="seller", buyer_uid="buyer", amount=25,
            event_id="settle-1", order_id="O1", trade_id="T1",
        )
        self.assertEqual(result["status"], "completed")
        seller = db["users"]["seller"]["wallet"]
        buyer = db["users"]["buyer"]["wallet"]
        self.assertEqual(seller["token_balance"], 75.0)
        self.assertEqual(seller["live_token_balance"], 40.0)
        self.assertEqual(seller["exchange_reserved_slh"], 15.0)
        self.assertEqual(buyer["token_balance"], 25.0)
        self.assertEqual(buyer["live_token_balance"], 25.0)


if __name__ == "__main__":
    unittest.main()
