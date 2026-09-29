import unittest

import handlers.webapp_data_handler as webapp


class _Bot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))


class WebAppExchangeCancelTests(unittest.TestCase):
    def test_sell_cancel_uses_canonical_release(self):
        db = {
            "users": {
                "seller": {
                    "wallet": {
                        # Reserve only moves live/spendable SLH into escrow.
                        "token_balance": 100.0,
                        "live_token_balance": 60.0,
                        "exchange_reserved_slh": 40.0,
                        "exchange_reserved_credits": 0.0,
                        "credits": 0.0,
                    }
                }
            },
            "exchange_orders": {
                "O1": {
                    "id": "O1",
                    "uid": "seller",
                    "side": "sell",
                    "original_amount": "40.00000000",
                    "remaining_amount": "40.00000000",
                    "limit_price": "1.00000000",
                    "reserved_slh": "40.00000000",
                    "reserved_credits": "0.00000000",
                    "sequence": 1,
                    "status": "open",
                }
            },
            "slh_token_ledger": [
                {
                    "event_id": "exchange:reserve_slh:O1",
                    "kind": "exchange_reserve",
                    "reason": "exchange:sell_reserve",
                    "from_uid": "seller",
                    "to_uid": "__EXCHANGE_RESERVE__",
                    "amount": 40.0,
                    "order_id": "O1",
                }
            ],
        }

        original_atomic_update = webapp.state_manager.atomic_update
        webapp.state_manager.atomic_update = lambda mutate: mutate(db)
        try:
            bot = _Bot()
            webapp._cancel(bot, 123, "seller", "O1")
        finally:
            webapp.state_manager.atomic_update = original_atomic_update

        wallet = db["users"]["seller"]["wallet"]
        self.assertEqual(wallet["token_balance"], 100.0)
        self.assertEqual(wallet["live_token_balance"], 60.0)
        self.assertEqual(wallet["exchange_reserved_slh"], 0.0)

        order = db["exchange_orders"]["O1"]
        self.assertEqual(order["status"], "cancelled")
        self.assertEqual(order["remaining_amount"], "0.00000000")
        self.assertEqual(order["reserved_slh"], "0.00000000")

        releases = [
            entry for entry in db["slh_token_ledger"]
            if entry.get("event_id") == "exchange:release_slh:O1"
        ]
        self.assertEqual(len(releases), 1)
        self.assertEqual(releases[0]["kind"], "exchange_release")
        self.assertEqual(releases[0]["amount"], 40.0)


if __name__ == "__main__":
    unittest.main()
