import unittest

from core.slh_distribution import (
    EXCHANGE_RESERVE_KEY,
    reserve_in_db,
    release_reserve_in_db,
    settle_reserve_in_db,
)
from handlers.exchange_handler import _place, cancel_order_in_db


def _db():
    return {
        "users": {
            "seller": {"wallet": {"token_balance": 100.0, EXCHANGE_RESERVE_KEY: 0.0}},
            "buyer": {"wallet": {"token_balance": 5.0, EXCHANGE_RESERVE_KEY: 0.0}},
        },
        "slh_token_ledger": [],
    }


def _supply(db):
    total = 0.0
    for user in db["users"].values():
        wallet = user["wallet"]
        total += float(wallet.get("token_balance", 0.0))
        total += float(wallet.get(EXCHANGE_RESERVE_KEY, 0.0))
    return total


class SlhExchangeSettlementTests(unittest.TestCase):
    def test_reserve_preserves_supply_and_is_replay_safe(self):
        db = _db()
        before = _supply(db)

        first = reserve_in_db(
            db, uid="seller", amount=40,
            event_id="exchange:reserve_slh:O1", order_id="O1",
        )
        second = reserve_in_db(
            db, uid="seller", amount=40,
            event_id="exchange:reserve_slh:O1", order_id="O1",
        )

        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "already_completed")
        self.assertEqual(db["users"]["seller"]["wallet"]["token_balance"], 60.0)
        self.assertEqual(db["users"]["seller"]["wallet"][EXCHANGE_RESERVE_KEY], 40.0)
        self.assertEqual(_supply(db), before)
        self.assertEqual(len(db["slh_token_ledger"]), 1)

    def test_settlement_moves_reserved_slh_without_minting(self):
        db = _db()
        before = _supply(db)

        reserve_in_db(
            db, uid="seller", amount=40,
            event_id="exchange:reserve_slh:O1", order_id="O1",
        )
        result = settle_reserve_in_db(
            db, seller_uid="seller", buyer_uid="buyer", amount=25,
            event_id="exchange:settlement_slh:T1",
            order_id="O1", trade_id="T1",
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(db["users"]["seller"]["wallet"]["token_balance"], 60.0)
        self.assertEqual(db["users"]["seller"]["wallet"][EXCHANGE_RESERVE_KEY], 15.0)
        self.assertEqual(db["users"]["buyer"]["wallet"]["token_balance"], 30.0)
        self.assertEqual(_supply(db), before)

        replay = settle_reserve_in_db(
            db, seller_uid="seller", buyer_uid="buyer", amount=25,
            event_id="exchange:settlement_slh:T1",
            order_id="O1", trade_id="T1",
        )
        self.assertEqual(replay["status"], "already_completed")
        self.assertEqual(_supply(db), before)

    def test_cancel_release_returns_reserved_slh(self):
        db = _db()
        before = _supply(db)

        reserve_in_db(
            db, uid="seller", amount=40,
            event_id="exchange:reserve_slh:O1", order_id="O1",
        )
        release = release_reserve_in_db(
            db, uid="seller", amount=40,
            event_id="exchange:release_slh:O1", order_id="O1",
        )

        self.assertEqual(release["status"], "completed")
        self.assertEqual(db["users"]["seller"]["wallet"]["token_balance"], 100.0)
        self.assertEqual(db["users"]["seller"]["wallet"][EXCHANGE_RESERVE_KEY], 0.0)
        self.assertEqual(_supply(db), before)
        self.assertEqual(len(db["slh_token_ledger"]), 2)

    def test_reserve_and_settlement_reject_insufficient_amount(self):
        db = _db()
        with self.assertRaises(ValueError):
            reserve_in_db(
                db, uid="seller", amount=101,
                event_id="exchange:reserve_slh:O1", order_id="O1",
            )
        reserve_in_db(
            db, uid="seller", amount=10,
            event_id="exchange:reserve_slh:O1", order_id="O1",
        )
        with self.assertRaises(ValueError):
            settle_reserve_in_db(
                db, seller_uid="seller", buyer_uid="buyer", amount=11,
                event_id="exchange:settlement_slh:T1",
                order_id="O1", trade_id="T1",
            )


    def test_cancel_syncs_request_state_and_preserves_recorded_fills(self):
        from handlers.exchange_handler import _order_filled

        db = {
            "users": {
                "seller": {"wallet": {"token_balance": 100.0, EXCHANGE_RESERVE_KEY: 0.0}},
            },
            "exchange_orders": {},
            "exchange_requests": {},
            "exchange_trades": [],
            "exchange_sequence": 0,
            "slh_token_ledger": [],
            "ledger": [],
        }

        result = _place(db, "seller", "sell", 10, 1, "SELL-1")
        self.assertEqual(result["status"], "open")
        oid = result["order_id"]

        cancel_order_in_db(db, "seller", oid)

        order = db["exchange_orders"][oid]
        request = db["exchange_requests"]["SELL-1"]
        self.assertEqual(order["status"], "cancelled")
        self.assertEqual(order["remaining_amount"], "0.00000000")
        self.assertEqual(request["status"], "cancelled")
        self.assertEqual(request["remaining"], "0.00000000")
        self.assertEqual(request["filled"], "0.00000000")
        self.assertEqual(db["users"]["seller"]["wallet"]["token_balance"], 100.0)
        self.assertEqual(db["users"]["seller"]["wallet"][EXCHANGE_RESERVE_KEY], 0.0)
        self.assertEqual(_order_filled(order), 0)

    def test_matched_orders_sync_both_requests(self):
        db = {
            "users": {
                "seller": {"wallet": {"token_balance": 100.0, EXCHANGE_RESERVE_KEY: 0.0}},
                "buyer": {"wallet": {"credits": 100.0, "exchange_reserved_credits": 0.0, "token_balance": 0.0, EXCHANGE_RESERVE_KEY: 0.0}},
            },
            "exchange_orders": {},
            "exchange_requests": {},
            "exchange_trades": [],
            "exchange_sequence": 0,
            "slh_token_ledger": [],
            "ledger": [],
        }

        sell = _place(db, "seller", "sell", 10, 1, "SELL-1")
        buy = _place(db, "buyer", "buy", 10, 1, "BUY-1")

        self.assertEqual(sell["status"], "open")
        self.assertEqual(buy["status"], "filled")
        self.assertEqual(db["exchange_requests"]["SELL-1"]["status"], "filled")
        self.assertEqual(db["exchange_requests"]["SELL-1"]["remaining"], "0.00000000")
        self.assertEqual(db["exchange_requests"]["SELL-1"]["filled"], "10.00000000")
        self.assertEqual(db["exchange_requests"]["BUY-1"]["status"], "filled")
        self.assertEqual(db["exchange_requests"]["BUY-1"]["remaining"], "0.00000000")
        self.assertEqual(db["exchange_requests"]["BUY-1"]["filled"], "10.00000000")


if __name__ == "__main__":
    unittest.main()
