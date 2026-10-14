import unittest
from datetime import datetime, timedelta, timezone

import webapp as rest_webapp


class ExchangeCandlesApiTests(unittest.TestCase):
    def setUp(self):
        self.db = {"exchange_trades": []}
        self.original_load_db = rest_webapp.load_db
        rest_webapp.load_db = lambda: self.db
        self.client = rest_webapp.app.test_client()

    def tearDown(self):
        rest_webapp.load_db = self.original_load_db

    def test_ohlc_aggregates_completed_trades_in_time_order(self):
        self.db["exchange_trades"] = [
            {
                "timestamp": "2026-10-14T15:04:00Z",
                "price": "2.0",
                "slh_amount": "2",
            },
            {
                "timestamp": "2026-10-14T15:01:00+00:00",
                "price": "1.0",
                "slh_amount": "1",
            },
            {
                "timestamp": "2026-10-14T15:16:00Z",
                "price": "1.5",
                "slh_amount": "0.5",
            },
            {"timestamp": "not-a-timestamp", "price": "999", "slh_amount": "100"},
            {"timestamp": "2026-10-14T15:17:00Z", "price": "NaN", "slh_amount": "1"},
            {"timestamp": "2026-10-14T15:18:00Z", "price": "1.2", "slh_amount": "-5"},
            "invalid-row",
        ]

        response = self.client.get("/api/v1/exchange/candles?interval=15m&limit=200")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["symbol"], "SLH/CREDITS")
        self.assertEqual(payload["interval"], "15m")
        self.assertEqual(payload["source"], "completed_internal_exchange_trades")
        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["count"], 2)

        first, second = payload["candles"]
        expected_first_bucket = int(
            datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc).timestamp()
        )
        expected_second_bucket = int(
            datetime(2026, 10, 14, 15, 15, tzinfo=timezone.utc).timestamp()
        )
        self.assertEqual(first, {
            "time": expected_first_bucket,
            "open": 1.0,
            "high": 2.0,
            "low": 1.0,
            "close": 2.0,
            "volume": 3.0,
        })
        self.assertEqual(second, {
            "time": expected_second_bucket,
            "open": 1.5,
            "high": 1.5,
            "low": 1.5,
            "close": 1.5,
            "volume": 0.5,
        })

    def test_invalid_interval_and_nonpositive_limit_are_rejected(self):
        invalid_interval = self.client.get(
            "/api/v1/exchange/candles?interval=10y"
        )
        self.assertEqual(invalid_interval.status_code, 400)
        self.assertEqual(invalid_interval.get_json()["error"], "INVALID_INTERVAL")

        for limit in ("0", "-1", "not-a-number"):
            with self.subTest(limit=limit):
                response = self.client.get(
                    "/api/v1/exchange/candles?interval=1h&limit=" + limit
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error"], "INVALID_LIMIT")

    def test_limit_is_bounded_and_results_are_newest_first_selection(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.db["exchange_trades"] = [
            {
                "timestamp": (start + timedelta(hours=i)).isoformat(),
                "price": str(i + 1),
                "slh_amount": "1",
            }
            for i in range(520)
        ]

        response = self.client.get("/api/v1/exchange/candles?interval=1h&limit=900")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["count"], 500)
        self.assertEqual(len(payload["candles"]), 500)
        self.assertEqual(payload["candles"][0]["open"], 21.0)
        self.assertEqual(payload["candles"][-1]["close"], 520.0)


if __name__ == "__main__":
    unittest.main()
