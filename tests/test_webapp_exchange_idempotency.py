import unittest
from unittest.mock import patch

import webapp


class WebAppExchangeIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.client = webapp.app.test_client()
        self.db = {
            "users": {
                "123": {
                    "wallet": {
                        "credits": 100.0,
                        "token_balance": 0.0,
                        "exchange_reserved_slh": 0.0,
                        "exchange_reserved_credits": 0.0,
                    }
                }
            },
            "exchange_orders": {},
            "exchange_trades": [],
            "exchange_requests": {},
            "exchange_sequence": 0,
            "ledger": [],
            "slh_token_ledger": [],
        }

    def _atomic_update(self, mutate):
        return mutate(self.db)

    def _post(self, request_id):
        return self.client.post(
            "/api/v1/exchange/order",
            json={
                "side": "buy",
                "amount": "1",
                "price": "1",
                "client_request_id": request_id,
            },
        )

    def test_same_client_request_is_replay_safe_but_new_request_creates_new_order(self):
        with patch("webapp.authenticated_uid", return_value="123"), patch(
            "webapp.state_manager.atomic_update", side_effect=self._atomic_update
        ):
            first = self._post("req-A")
            replay = self._post("req-A")
            second = self._post("req-B")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(second.status_code, 200)

        first_json = first.get_json()
        replay_json = replay.get_json()
        second_json = second.get_json()

        self.assertEqual(replay_json, first_json)
        self.assertNotEqual(second_json["order_id"], first_json["order_id"])

        self.assertEqual(len(self.db["exchange_orders"]), 2)
        self.assertEqual(len(self.db["exchange_requests"]), 2)
        self.assertEqual(self.db["users"]["123"]["wallet"]["credits"], 98.0)
        self.assertEqual(self.db["users"]["123"]["wallet"]["exchange_reserved_credits"], 2.0)


if __name__ == "__main__":
    unittest.main()
