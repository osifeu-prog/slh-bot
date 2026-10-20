import os
import unittest
from unittest import mock

from core import stars_gate, stars_invoice


class StarsStoreGateTest(unittest.TestCase):
    def test_store_sales_default_closed(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(stars_gate.store_stars_sales_open())

    def test_only_explicit_one_opens_store_sales(self):
        for value in ("", "0", "true", "yes", "2"):
            with self.subTest(value=value), mock.patch.dict(
                os.environ, {"STARS_STORE_SALES_OPEN": value}
            ):
                self.assertFalse(stars_gate.store_stars_sales_open())
        with mock.patch.dict(os.environ, {"STARS_STORE_SALES_OPEN": "1"}):
            self.assertTrue(stars_gate.store_stars_sales_open())

    def test_closed_store_invoice_never_calls_telegram(self):
        req = {
            "title": "SLH Store · emoji_vip",
            "description": "SLH Store item",
            "payload": "item_emoji_vip_123",
            "stars": 100,
        }
        with mock.patch.dict(
            os.environ,
            {"BOT_TOKEN": "123:test", "STARS_PAYMENTS_OPEN": "1", "STARS_STORE_SALES_OPEN": "0"},
        ), mock.patch("core.stars_invoice.requests.post") as post:
            with self.assertRaisesRegex(RuntimeError, "STARS_STORE_SALES_CLOSED"):
                stars_invoice.create_invoice_link(req)
            post.assert_not_called()

    def test_open_store_invoice_uses_telegram_stars(self):
        req = {
            "title": "SLH Store · course_ethereum",
            "description": "SLH Store item",
            "payload": "item_course_ethereum_123",
            "stars": 299,
        }
        response = mock.Mock()
        response.json.return_value = {
            "ok": True,
            "result": "https://t.me/$test-invoice",
        }
        with mock.patch.dict(
            os.environ,
            {"BOT_TOKEN": "123:test", "STARS_PAYMENTS_OPEN": "1", "STARS_STORE_SALES_OPEN": "1"},
        ), mock.patch(
            "core.stars_invoice.requests.post", return_value=response
        ) as post:
            link = stars_invoice.create_invoice_link(req)
        self.assertEqual(link, "https://t.me/$test-invoice")
        self.assertEqual(post.call_args.kwargs["json"]["currency"], "XTR")
        self.assertEqual(post.call_args.kwargs["json"]["prices"][0]["amount"], 299)

    def test_only_reviewed_user_scoped_products_are_allowlisted(self):
        expected = {
            "course_ethereum",
            "course_slh_vs_eth_sol",
            "course_algo_trading",
            "trade_pro",
        }
        self.assertEqual(stars_gate.SELLABLE_STORE_STARS_ITEM_IDS, frozenset(expected))
        for item_id in expected:
            self.assertTrue(stars_gate.store_stars_item_allowed(item_id))
        for item_id in ("emoji_bitcoin", "emoji_slh", "emoji_vip", "agent_os", "esp32_pro"):
            self.assertFalse(stars_gate.store_stars_item_allowed(item_id))

    def test_catalog_filter_hides_unapproved_skus_and_preserves_prices(self):
        configured = {
            "course_ethereum": 299,
            "trade_pro": 499,
            "emoji_slh": 10,
            "agent_os": 199,
            "esp32_pro": 888,
        }
        original = dict(configured)

        filtered = stars_gate.filter_store_stars_items(configured)

        self.assertEqual(filtered, {
            "course_ethereum": 299,
            "trade_pro": 499,
        })
        self.assertEqual(configured, original)

    def test_unapproved_item_never_calls_telegram_even_when_global_gate_is_open(self):
        req = {
            "title": "SLH Store · emoji_vip",
            "description": "SLH Store item",
            "payload": "item_emoji_vip_123",
            "stars": 100,
        }
        with mock.patch.dict(
            os.environ,
            {"BOT_TOKEN": "123:test", "STARS_PAYMENTS_OPEN": "1", "STARS_STORE_SALES_OPEN": "1"},
        ), mock.patch("core.stars_invoice.requests.post") as post:
            with self.assertRaisesRegex(RuntimeError, "STARS_STORE_ITEM_NOT_AVAILABLE"):
                stars_invoice.create_invoice_link(req)
            post.assert_not_called()

    def test_item_gate_requires_both_global_opt_in_and_allowlist(self):
        with mock.patch.dict(os.environ, {"STARS_STORE_SALES_OPEN": "0"}):
            self.assertFalse(stars_gate.store_stars_item_sales_open("course_ethereum"))
        with mock.patch.dict(os.environ, {"STARS_STORE_SALES_OPEN": "1"}):
            self.assertTrue(stars_gate.store_stars_item_sales_open("course_ethereum"))
            self.assertFalse(stars_gate.store_stars_item_sales_open("emoji_slh"))

    def test_credits_invoice_is_not_controlled_by_store_gate(self):
        req = {
            "title": "100 Credits",
            "description": "Credits pack",
            "payload": "credits_100_123",
            "stars": 100,
        }
        response = mock.Mock()
        response.json.return_value = {
            "ok": True,
            "result": "https://t.me/$credits-invoice",
        }
        with mock.patch.dict(
            os.environ,
            {"BOT_TOKEN": "123:test", "STARS_PAYMENTS_OPEN": "1", "STARS_STORE_SALES_OPEN": "0"},
        ), mock.patch(
            "core.stars_invoice.requests.post", return_value=response
        ) as post:
            link = stars_invoice.create_invoice_link(req)
        self.assertEqual(link, "https://t.me/$credits-invoice")
        post.assert_called_once()

    def test_non_one_gate_rejects_final_boundary(self):
        with mock.patch.dict(os.environ, {"STARS_STORE_SALES_OPEN": "0"}):
            with self.assertRaisesRegex(RuntimeError, "STARS_STORE_SALES_CLOSED"):
                stars_gate.require_store_stars_sales_open("course_ethereum")


if __name__ == "__main__":
    unittest.main()
