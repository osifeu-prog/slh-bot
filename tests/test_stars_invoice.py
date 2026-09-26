import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.stars_invoice import (
    build_credit_payload,
    build_item_payload,
    build_vip_payload,
    parse_invoice_payload,
)


class StarsInvoicePayloadTests(unittest.TestCase):
    def test_credit_payload_round_trip(self):
        self.assertEqual(
            parse_invoice_payload(build_credit_payload(550, "100")),
            {"kind": "credits", "credits": 550, "uid": "100"},
        )

    def test_item_payload_round_trip(self):
        self.assertEqual(
            parse_invoice_payload(build_item_payload("course_ethereum", "100")),
            {"kind": "item", "item_id": "course_ethereum", "uid": "100"},
        )

    def test_vip_payload_round_trip(self):
        self.assertEqual(
            parse_invoice_payload(build_vip_payload("100")),
            {"kind": "vip", "uid": "100"},
        )

    def test_invalid_payload(self):
        for value in ("credits_bad_100", "credits_100_", "other_100_100", "item_x"):
            self.assertIsNone(parse_invoice_payload(value))


class StarsInvoiceApiTests(unittest.TestCase):
    def setUp(self):
        from webapp import app
        self.client = app.test_client()

    def test_invalid_auth(self):
        with patch("webapp.authenticated_uid", return_value=None):
            response = self.client.post(
                "/api/v1/stars/invoice",
                json={"kind": "credit_pack", "id": "100credits"},
            )
        self.assertEqual(response.status_code, 401)

    def test_unknown_pack(self):
        with patch("webapp.authenticated_uid", return_value="100"):
            response = self.client.post(
                "/api/v1/stars/invoice",
                json={"kind": "credit_pack", "id": "missing"},
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"], "CREDIT_PACK_NOT_FOUND")

    def test_client_price_is_ignored(self):
        fake = {
            "link": "https://t.me/$TEST",
            "kind": "credit_pack",
            "id": "100credits",
            "stars": 100,
            "currency": "XTR",
        }
        with patch("webapp.authenticated_uid", return_value="100"), patch(
            "core.stars_invoice.create_invoice_link_for_purchase",
            return_value=fake,
        ) as create:
            response = self.client.post(
                "/api/v1/stars/invoice",
                json={
                    "kind": "credit_pack",
                    "id": "100credits",
                    "stars": 999999,
                    "price": 0.01,
                    "client_request_id": "req-1",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["stars"], 100)
        create.assert_called_once_with(
            uid="100", kind="credit_pack", item_id="100credits"
        )

    def test_invoice_uses_canonical_server_price(self):
        bot = Mock()
        bot.create_invoice_link.return_value = "https://t.me/$TEST"
        with patch("core.stars_invoice._INVOICE_BOT", bot):
            from core.stars_invoice import create_invoice_link_for_purchase

            result = create_invoice_link_for_purchase(
                uid="100", kind="credit_pack", item_id="500credits"
            )

        self.assertEqual(result["stars"], 500)
        args = bot.create_invoice_link.call_args.kwargs
        self.assertEqual(args["currency"], "XTR")
        self.assertIsNone(args["provider_token"])
        self.assertEqual(args["prices"][0].amount, 500)

    def test_mini_app_has_no_send_data(self):
        html = Path(__file__).resolve().parents[1].joinpath("mini_app.html").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("sendData", html)
        self.assertIn("/api/v1/stars/invoice", html)
        self.assertIn("openInvoice", html)

    def test_revenue_buttons_do_not_use_command_sender(self):
        html = Path(__file__).resolve().parents[1].joinpath("mini_app.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("openCreditsPicker(this)", html)
        self.assertIn("buyStarsProduct('store_item','emoji_bitcoin',this)", html)
        self.assertNotIn("openAction('/pay'", html)
        self.assertNotIn("openAction('/buystars", html)


if __name__ == "__main__":
    unittest.main()
