import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core import stars_gate as financial_gates
from handlers import payment_handler
from handlers import stars_store


class FakeBot:
    def __init__(self):
        self.message_handlers = []
        self.callback_handlers = []
        self.pre_checkout_handlers = []
        self.sent_messages = []
        self.reply_messages = []
        self.callback_answers = []
        self.pre_checkout_answers = []
        self.invoices = []
        self.invoice_links = []

    def message_handler(self, **options):
        def decorate(fn):
            self.message_handlers.append((options, fn))
            return fn
        return decorate

    def callback_query_handler(self, **options):
        def decorate(fn):
            self.callback_handlers.append((options, fn))
            return fn
        return decorate

    def pre_checkout_query_handler(self, **options):
        def decorate(fn):
            self.pre_checkout_handlers.append((options, fn))
            return fn
        return decorate

    def send_message(self, chat_id, text, **kwargs):
        self.sent_messages.append((chat_id, text, kwargs))

    def reply_to(self, message, text, **kwargs):
        self.reply_messages.append((message, text, kwargs))

    def answer_callback_query(self, callback_id, text=None, **kwargs):
        self.callback_answers.append((callback_id, text, kwargs))

    def answer_pre_checkout_query(self, query_id, **kwargs):
        self.pre_checkout_answers.append((query_id, kwargs))

    def send_invoice(self, **kwargs):
        self.invoices.append(kwargs)

    def create_invoice_link(self, **kwargs):
        self.invoice_links.append(kwargs)
        return "https://example.invalid/stars-invoice"

    def edit_message_text(self, **kwargs):
        pass

    @staticmethod
    def _matches(options, command):
        return command in options.get("commands", [])

    def message(self, command):
        for options, fn in self.message_handlers:
            if self._matches(options, command):
                return fn
        raise AssertionError(f"message handler not found: {command}")

    def callback(self, data):
        call = SimpleNamespace(data=data)
        for options, fn in self.callback_handlers:
            predicate = options.get("func")
            if predicate is None or predicate(call):
                return fn
        raise AssertionError(f"callback handler not found: {data}")

    def pre_checkout(self):
        if not self.pre_checkout_handlers:
            raise AssertionError("pre-checkout handler not found")
        return self.pre_checkout_handlers[0][1]

    def successful_payment(self):
        for options, fn in self.message_handlers:
            if "successful_payment" in options.get("content_types", []):
                return fn
        raise AssertionError("successful_payment handler not found")


def _message(uid="12345", text="/pay"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=uid),
        chat=SimpleNamespace(id=77),
        text=text,
    )


def _callback(data="pay_100credits", uid="12345"):
    return SimpleNamespace(
        id="callback-1",
        data=data,
        from_user=SimpleNamespace(id=uid),
        message=SimpleNamespace(
            chat=SimpleNamespace(id=77),
            message_id=101,
        ),
    )


def _pre_checkout(uid="12345", payload="credits_100_12345", amount=100, currency="XTR"):
    return SimpleNamespace(
        id="checkout-1",
        invoice_payload=payload,
        total_amount=amount,
        currency=currency,
        from_user=SimpleNamespace(id=uid),
    )


class StarsPaymentAvailabilityGateTests(unittest.TestCase):
    def test_gate_is_closed_by_default_and_requires_exact_opt_in(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(financial_gates.stars_payments_open())
        with patch.dict(os.environ, {"STARS_PAYMENTS_OPEN": "0"}, clear=True):
            self.assertFalse(financial_gates.stars_payments_open())
        with patch.dict(os.environ, {"STARS_PAYMENTS_OPEN": "true"}, clear=True):
            self.assertFalse(financial_gates.stars_payments_open())
        with patch.dict(os.environ, {"STARS_PAYMENTS_OPEN": "1"}, clear=True):
            self.assertTrue(financial_gates.stars_payments_open())

    def test_pay_menu_and_vip_invoice_are_closed_by_default(self):
        bot = FakeBot()
        payment_handler.register_payment_handlers(bot)
        db = {"users": {"12345": {"vip_access_until": 0}}}
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(payment_handler.state_manager, "load_db", return_value=db),
        ):
            bot.message("pay")(_message(text="/pay"))
            bot.message("vip")(_message(text="/vip"))

        self.assertEqual(bot.invoices, [])
        self.assertEqual(bot.invoice_links, [])
        self.assertEqual(len(bot.sent_messages), 2)
        self.assertTrue(all("סגורים" in item[1] for item in bot.sent_messages))

    def test_credit_invoice_callback_is_blocked_when_gate_is_closed(self):
        bot = FakeBot()
        payment_handler.register_payment_handlers(bot)
        with patch.dict(os.environ, {"STARS_PAYMENTS_OPEN": "0"}, clear=True):
            bot.callback("pay_100credits")(_callback())

        self.assertEqual(bot.invoices, [])
        self.assertIn("סגורים", (bot.callback_answers[0][1] or ""))

    def test_precheckout_is_rejected_after_gate_closes(self):
        bot = FakeBot()
        payment_handler.register_payment_handlers(bot)
        with patch.dict(os.environ, {"STARS_PAYMENTS_OPEN": "0"}, clear=True):
            bot.pre_checkout()(_pre_checkout())

        self.assertEqual(bot.pre_checkout_answers, [(
            "checkout-1",
            {
                "ok": False,
                "error_message": "SLH Stars payments are temporarily closed.",
            },
        )])

    def test_store_stars_invoice_is_blocked_when_gate_is_closed(self):
        bot = FakeBot()
        stars_store.register(bot)
        with patch.dict(os.environ, {"STARS_PAYMENTS_OPEN": "0"}, clear=True):
            bot.message("buystars")(_message(text="/buystars emoji_slh"))

        self.assertEqual(bot.invoices, [])
        self.assertIn("סגורים", bot.reply_messages[0][1])

    def test_open_credit_callback_can_create_an_invoice(self):
        bot = FakeBot()
        payment_handler.register_payment_handlers(bot)
        with patch.dict(os.environ, {"STARS_PAYMENTS_OPEN": "1"}, clear=True):
            bot.callback("pay_100credits")(_callback())

        self.assertEqual(len(bot.invoices), 1)
        invoice = bot.invoices[0]
        self.assertEqual(invoice["invoice_payload"], "credits_100_12345")
        self.assertEqual(invoice["currency"], "XTR")
        self.assertEqual(invoice["prices"][0].amount, 100)

    def test_open_precheckout_accepts_a_valid_credits_package(self):
        bot = FakeBot()
        payment_handler.register_payment_handlers(bot)
        with patch.dict(os.environ, {"STARS_PAYMENTS_OPEN": "1"}, clear=True):
            bot.pre_checkout()(_pre_checkout())

        self.assertEqual(bot.pre_checkout_answers, [("checkout-1", {"ok": True})])

    def test_open_store_stars_route_can_create_an_invoice(self):
        bot = FakeBot()
        stars_store.register(bot)
        items = {"emoji_slh": {"name": "SLH Emoji Pack"}}
        with (
            patch.dict(os.environ, {"STARS_PAYMENTS_OPEN": "1"}, clear=True),
            patch.object(stars_store, "load_items", return_value=items),
            patch.object(stars_store, "resolve_item_id", return_value="emoji_slh"),
            patch.object(stars_store, "get_stars_price", return_value=50),
        ):
            bot.message("buystars")(_message(text="/buystars emoji_slh"))

        self.assertEqual(len(bot.invoices), 1)
        self.assertEqual(bot.invoices[0]["invoice_payload"], "item_emoji_slh_12345")
        self.assertEqual(bot.invoices[0]["prices"][0].amount, 50)

    def test_confirmed_successful_payment_is_processed_even_when_new_payments_closed(self):
        bot = FakeBot()
        payment_handler.register_payment_handlers(bot)
        payment = SimpleNamespace(
            invoice_payload="credits_100_12345",
            total_amount=100,
            currency="XTR",
            telegram_payment_charge_id="confirmed-charge-id",
            provider_payment_charge_id=None,
        )
        message = _message(text="")
        message.successful_payment = payment
        with (
            patch.dict(os.environ, {"STARS_PAYMENTS_OPEN": "0"}, clear=True),
            patch.object(payment_handler.state_manager, "load_db", return_value={"users": {"12345": {}}}),
            patch.object(
                payment_handler.stars_payment_authority,
                "record_stars_payment",
                return_value={"status": "applied", "credits": 100},
            ) as record_payment,
        ):
            bot.successful_payment()(message)

        record_payment.assert_called_once()
        self.assertEqual(record_payment.call_args.kwargs["telegram_payment_charge_id"], "confirmed-charge-id")
        self.assertTrue(any("100 credits added" in text for _, text, _ in bot.sent_messages))


if __name__ == "__main__":
    unittest.main()
