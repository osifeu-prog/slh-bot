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
            {"BOT_TOKEN": "123:test", "STARS_STORE_SALES_OPEN": "0"},
        ), mock.patch("core.stars_invoice.requests.post") as post:
            with self.assertRaisesRegex(RuntimeError, "STARS_STORE_SALES_CLOSED"):
                stars_invoice.create_invoice_link(req)
            post.assert_not_called()

    def test_open_store_invoice_uses_telegram_stars(self):
        req = {
            "title": "SLH Store · emoji_vip",
            "description": "SLH Store item",
            "payload": "item_emoji_vip_123",
            "stars": 100,
        }
        response = mock.Mock()
        response.json.return_value = {
            "ok": True,
            "result": "https://t.me/$test-invoice",
        }
        with mock.patch.dict(
            os.environ,
            {"BOT_TOKEN": "123:test", "STARS_STORE_SALES_OPEN": "1"},
        ), mock.patch(
            "core.stars_invoice.requests.post", return_value=response
        ) as post:
            link = stars_invoice.create_invoice_link(req)
        self.assertEqual(link, "https://t.me/$test-invoice")
        self.assertEqual(post.call_args.kwargs["json"]["currency"], "XTR")
        self.assertEqual(post.call_args.kwargs["json"]["prices"][0]["amount"], 100)

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
            {"BOT_TOKEN": "123:test", "STARS_STORE_SALES_OPEN": "0"},
        ), mock.patch(
            "core.stars_invoice.requests.post", return_value=response
        ) as post:
            link = stars_invoice.create_invoice_link(req)
        self.assertEqual(link, "https://t.me/$credits-invoice")
        post.assert_called_once()

    def test_non_one_gate_rejects_final_boundary(self):
        with mock.patch.dict(os.environ, {"STARS_STORE_SALES_OPEN": "0"}):
            with self.assertRaisesRegex(RuntimeError, "STARS_STORE_SALES_CLOSED"):
                stars_gate.require_store_stars_sales_open()


if __name__ == "__main__":
    unittest.main()
