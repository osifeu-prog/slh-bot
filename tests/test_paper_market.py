import os
import unittest
from unittest.mock import patch

from core import paper_market


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class PaperMarketAdapterTests(unittest.TestCase):
    def setUp(self):
        with paper_market._LOCK:
            paper_market._CACHE["payload"] = None
            paper_market._CACHE["expires_at"] = 0

    def test_missing_provider_key_fails_closed_without_quotes(self):
        with patch.dict(os.environ, {"TWELVEDATA_API_KEY": ""}, clear=False):
            result = paper_market.market_snapshot(force=True)
        self.assertEqual(result["status"], "DATA_PROVIDER_NOT_CONFIGURED")
        self.assertEqual(result["tiles"], [])
        self.assertTrue(result["paper_only"])
        self.assertNotIn("api_key", str(result).lower())

    def test_valid_batch_quotes_are_sanitized_and_allowlisted(self):
        payload = {
            "SPY": {"symbol": "SPY", "price": "500.5", "percent_change": "1.25", "datetime": "2026-10-18"},
            "QQQ": {"symbol": "QQQ", "price": "600", "percent_change": "-0.5", "datetime": "2026-10-18"},
            "secret": {"symbol": "SECRET", "price": "1", "percent_change": "999"},
        }
        with patch.dict(os.environ, {"TWELVEDATA_API_KEY": "test-secret"}, clear=False), patch(
            "core.paper_market.requests.get", return_value=FakeResponse(payload)
        ) as get:
            result = paper_market.market_snapshot(force=True, now=100)
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual({x["symbol"] for x in result["tiles"]}, {"SPY", "QQQ"})
        self.assertNotIn("SECRET", str(result))
        self.assertNotIn("test-secret", str(result))
        self.assertEqual(result["tiles"][0]["symbol"], "SPY")
        self.assertEqual(result["tiles"][0]["price"], 500.5)
        self.assertEqual(result["tiles"][0]["change_percent"], 1.25)
        self.assertIn("Authorization", get.call_args.kwargs["headers"])
        self.assertNotIn("test-secret", get.call_args.kwargs["url"] if "url" in get.call_args.kwargs else get.call_args.args[0])

    def test_provider_error_returns_generic_blocked_state(self):
        with patch.dict(os.environ, {"TWELVEDATA_API_KEY": "test-secret"}, clear=False), patch(
            "core.paper_market.requests.get", side_effect=RuntimeError("test-secret raw provider body")
        ):
            result = paper_market.market_snapshot(force=True)
        self.assertEqual(result["status"], "PROVIDER_UNAVAILABLE")
        self.assertEqual(result["tiles"], [])
        self.assertNotIn("test-secret", str(result))
        self.assertNotIn("raw provider body", str(result))

    def test_summary_is_descriptive_not_a_buy_sell_instruction(self):
        snapshot = {"tiles": [
            {"symbol": "SPY", "change_percent": 1.5},
            {"symbol": "QQQ", "change_percent": -0.25},
        ]}
        summary = paper_market.market_lab_summary(snapshot)
        self.assertEqual(summary["status"], "DESCRIPTIVE_ONLY")
        self.assertEqual(summary["top_relative_move"]["symbol"], "SPY")
        self.assertEqual(summary["bottom_relative_move"]["symbol"], "QQQ")
        self.assertNotIn("buy", str(summary).lower())
        self.assertNotIn("sell", str(summary).lower())


if __name__ == "__main__":
    unittest.main()
