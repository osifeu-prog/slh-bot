import unittest
from unittest import mock

from core import stars_invoice
from core.stars_price_authority import (
    CREDIT_PACKS,
    VIP_MONTHLY_STARS,
    VIP_SUBSCRIPTION_PERIOD,
)


class StarsInvoiceTest(unittest.TestCase):
    def test_credit_pack_uses_server_authority(self):
        pack = CREDIT_PACKS[0]
        req = stars_invoice.build_invoice_request("123", "credit_pack", str(pack.stars))
        self.assertEqual(req["stars"], int(pack.stars))
        self.assertEqual(req["payload"], f"credits_{int(pack.credits)}_123")

    def test_unknown_pack_rejected(self):
        with self.assertRaises(ValueError):
            stars_invoice.build_invoice_request("123", "credit_pack", "7")

    def test_invalid_uid_rejected(self):
        with self.assertRaises(ValueError):
            stars_invoice.build_invoice_request("abc", "credit_pack", "100")

    def test_store_item_uses_catalog_price(self):
        with mock.patch("store.stars_purchase_service.get_stars_price", return_value=50):
            req = stars_invoice.build_invoice_request("123", "store_item", "emoji_vip")
        self.assertEqual(req["payload"], "item_emoji_vip_123")
        self.assertEqual(req["stars"], 50)

    def test_bad_store_item_rejected(self):
        with mock.patch("store.stars_purchase_service.get_stars_price", return_value=None):
            with self.assertRaises(ValueError):
                stars_invoice.build_invoice_request("123", "store_item", "nope")
        with self.assertRaises(ValueError):
            stars_invoice.build_invoice_request("123", "store_item", "../x")

    def test_vip_uses_existing_payload_and_authority(self):
        req = stars_invoice.build_invoice_request("123", "vip_monthly", "vip_monthly")
        self.assertEqual(req["stars"], VIP_MONTHLY_STARS)
        self.assertEqual(req["payload"], "vip_monthly_123")

    def test_create_link_uses_xtr(self):
        fake = mock.Mock()
        fake.json.return_value = {"ok": True, "result": "https://t.me/$abc"}
        with (
            mock.patch.dict("os.environ", {"BOT_TOKEN": "1:x"}),
            mock.patch("core.stars_invoice.requests.post", return_value=fake) as post,
        ):
            link = stars_invoice.create_invoice_link(
                {
                    "title": "100 Credits",
                    "description": "d",
                    "payload": "credits_100_1",
                    "stars": 100,
                }
            )
        self.assertEqual(link, "https://t.me/$abc")
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["currency"], "XTR")
        self.assertEqual(body["prices"][0]["amount"], 100)
        self.assertNotIn("provider_token", body)
        self.assertNotIn("subscription_period", body)

    def test_create_link_includes_subscription_period_for_vip(self):
        req = stars_invoice.build_invoice_request("123", "vip_monthly", "vip_monthly")
        fake = mock.Mock()
        fake.json.return_value = {"ok": True, "result": "https://t.me/$vip"}
        with (
            mock.patch.dict("os.environ", {"BOT_TOKEN": "1:x"}),
            mock.patch("core.stars_invoice.requests.post", return_value=fake) as post,
        ):
            stars_invoice.create_invoice_link(req)
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["currency"], "XTR")
        self.assertEqual(body["prices"][0]["amount"], VIP_MONTHLY_STARS)
        self.assertEqual(body["subscription_period"], VIP_SUBSCRIPTION_PERIOD)


if __name__ == "__main__":
    unittest.main()
