import unittest

from handlers import exchange_handler as exchange
from core.slh_distribution import (
    _release_reserved_in_db,
    _reserve_in_db,
    _settle_reserved_in_db,
)


def make_db():
    return {
        "users": {
            "seller": {"wallet": {
                "credits": 0.0,
                "token_balance": 100.0,
                "exchange_reserved_slh": 0.0,
                "exchange_reserved_credits": 0.0,
            }},
            "buyer": {"wallet": {
                "credits": 100.0,
                "token_balance": 0.0,
                "exchange_reserved_slh": 0.0,
                "exchange_reserved_credits": 0.0,
            }},
        }
    }


class SlhExchangeAuthorityTests(unittest.TestCase):
    def test_sell_reserve_and_cancel_release_preserve_supply(self):
        db = make_db()

        _reserve_in_db(db, uid="seller", amount=25, order_id="O1")

        self.assertEqual(db["users"]["seller"]["wallet"]["token_balance"], 75.0)
        self.assertEqual(db["users"]["seller"]["wallet"]["exchange_reserved_slh"], 25.0)

        _release_reserved_in_db(db, uid="seller", amount=25, order_id="O1")

        self.assertEqual(db["users"]["seller"]["wallet"]["token_balance"], 100.0)
        self.assertEqual(db["users"]["seller"]["wallet"]["exchange_reserved_slh"], 0.0)

    def test_settlement_moves_reserved_slh_and_is_replay_safe(self):
        db = make_db()
        _reserve_in_db(db, uid="seller", amount=10, order_id="O1")

        first = _settle_reserved_in_db(
            db,
            seller_uid="seller",
            buyer_uid="buyer",
            amount=10,
            event_id="exchange:T1:slh",
            trade_id="T1",
            sell_order_id="O1",
            buy_order_id="O2",
        )
        second = _settle_reserved_in_db(
            db,
            seller_uid="seller",
            buyer_uid="buyer",
            amount=10,
            event_id="exchange:T1:slh",
            trade_id="T1",
            sell_order_id="O1",
            buy_order_id="O2",
        )

        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "already_completed")
        self.assertEqual(db["users"]["seller"]["wallet"]["token_balance"], 90.0)
        self.assertEqual(db["users"]["seller"]["wallet"]["exchange_reserved_slh"], 0.0)
        self.assertEqual(db["users"]["buyer"]["wallet"]["token_balance"], 10.0)
        self.assertEqual(len(db["slh_token_ledger"]), 1)

    def test_partial_fill_keeps_reserve_invariants(self):
        db = make_db()

        sell = exchange._place(db, "seller", "sell", exchange._dec("10", "amount"), exchange._dec("2", "price"), "sell-1")
        self.assertEqual(sell["remaining"], "10.00000000")

        buy = exchange._place(db, "buyer", "buy", exchange._dec("4", "amount"), exchange._dec("2", "price"), "buy-1")

        self.assertEqual(buy["filled"], "4.00000000")
        self.assertEqual(buy["remaining"], "0.00000000")
        self.assertEqual(db["users"]["seller"]["wallet"]["token_balance"], 90.0)
        self.assertEqual(db["users"]["seller"]["wallet"]["exchange_reserved_slh"], 6.0)
        self.assertEqual(db["users"]["buyer"]["wallet"]["token_balance"], 4.0)
        self.assertEqual(db["users"]["buyer"]["wallet"]["credits"], 92.0)
        self.assertEqual(len(db["slh_token_ledger"]), 1)

    def test_exchange_settlement_conserves_total_slh(self):
        db = make_db()
        before = sum(
            float(u["wallet"].get("token_balance", 0))
            + float(u["wallet"].get("exchange_reserved_slh", 0))
            for u in db["users"].values()
        )

        exchange._place(
            db, "seller", "sell",
            exchange._dec("30", "amount"),
            exchange._dec("1", "price"),
            "sell-1",
        )
        exchange._place(
            db, "buyer", "buy",
            exchange._dec("30", "amount"),
            exchange._dec("1", "price"),
            "buy-1",
        )

        after = sum(
            float(u["wallet"].get("token_balance", 0))
            + float(u["wallet"].get("exchange_reserved_slh", 0))
            for u in db["users"].values()
        )
        self.assertEqual(before, after)
        self.assertEqual(len(db["slh_token_ledger"]), 1)


if __name__ == "__main__":
    unittest.main()
