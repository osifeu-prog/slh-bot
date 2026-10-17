import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from handlers import payment_handler, stars_store
from core.stars_price_authority import TELEGRAM_STARS_CURRENCY, VIP_MONTHLY_STARS


UID = 12345
CHAT_ID = 54321


class FakeBot:
    def __init__(self):
        self.handlers = []
        self.invoices = []
        self.messages = []
        self.replies = []
        self.callback_answers = []
        self.precheckout_answers = []
        self.invoice_links = []

    def _register(self, kind, options):
        def decorator(fn):
            self.handlers.append((kind, options, fn))
            return fn
        return decorator

    def message_handler(self, **options):
        return self._register("message", options)

    def callback_query_handler(self, **options):
        return self._register("callback", options)

    def pre_checkout_query_handler(self, **options):
        return self._register("pre_checkout", options)

    def _handler(self, kind, name):
        for registered_kind, _options, fn in self.handlers:
            if registered_kind == kind and fn.__name__ == name:
                return fn
        raise AssertionError(f"handler not registered: {kind}:{name}")

    def send_invoice(self, **kwargs):
        self.invoices.append(kwargs)

    def send_message(self, *args, **kwargs):
        self.messages.append((args, kwargs))

    def reply_to(self, *args, **kwargs):
        self.replies.append((args, kwargs))

    def answer_callback_query(self, *args, **kwargs):
        self.callback_answers.append((args, kwargs))

    def answer_pre_checkout_query(self, *args, **kwargs):
        self.precheckout_answers.append((args, kwargs))

    def create_invoice_link(self, **kwargs):
        self.invoice_links.append(kwargs)
        return "https://t.me/$test-invoice-link"


def _message(text):
    return SimpleNamespace(
        text=text,
        from_user=SimpleNamespace(id=UID),
        chat=SimpleNamespace(id=CHAT_ID),
    )


def _callback(data):
    return SimpleNamespace(
        id="callback-123",
        data=data,
        from_user=SimpleNamespace(id=UID),
        message=SimpleNamespace(chat=SimpleNamespace(id=CHAT_ID)),
    )


def _pre_checkout(payload, *, uid=UID, amount, currency=TELEGRAM_STARS_CURRENCY):
    return SimpleNamespace(
        id="checkout-123",
        invoice_payload=payload,
        from_user=SimpleNamespace(id=uid),
        total_amount=amount,
        currency=currency,
    )


class TelegramStarsAvailabilityGateTests(unittest.TestCase):
    def setUp(self):
        self.bot = FakeBot()
        payment_handler.register_payment_handlers(self.bot)
        stars_store.register(self.bot)

    def _first_pack(self):
        return next(iter(payment_handler.STARS_PACKS.items()))

    def _answer(self):
        return self.bot.precheckout_answers[-1][1]

    def test_gate_defaults_closed(self):
        with patch.dict(os.environ, {"STARS_PAYMENTS_OPEN": ""}, clear=False):
            with patch.dict(os.environ):
                os.environ.pop("STARS_PAYMENTS_OPEN", None)
                self.bot._handler("message", "pay_command")(_message("/pay"))
                self.assertEqual(self.bot.invoices, [])
                self.assertTrue(any("סגורים" in kwargs.get("text", "") for _args, kwargs in self.bot.messages))

    def test_pay_menu_and_credit_invoice_are_blocked_when_gate_closed(self):
        self.bot._handler("message", "pay_command")(_message("/pay"))
        pack_id, _package = self._first_pack()
        self.bot._handler("callback", "payment_callback")(_callback(f"pay_{pack_id}"))

        self.assertEqual(self.bot.invoices, [])
        self.assertTrue(self.bot.callback_answers)
        self.assertIn("closed", str(self.bot.callback_answers[-1]).lower())

    def test_vip_invoice_is_blocked_when_gate_closed(self):
        with patch.object(
            payment_handler.state_manager,
            "load_db",
            return_value={"users": {str(UID): {"vip_access_until": 0}}},
        ):
            self.bot._handler("message", "vip_command")(_message("/vip"))

        self.assertEqual(self.bot.invoice_links, [])
        self.assertTrue(any("סגורים" in str(message) for message in self.bot.messages))

    def test_store_stars_invoice_is_blocked_when_gate_closed(self):
        self.bot._handler("message", "buystars")(_message("/buystars emoji_slh"))
        self.assertEqual(self.bot.invoices, [])
        self.assertTrue(any("סגורים" in str(reply) for reply in self.bot.replies))

    def test_precheckout_rejects_stale_invoice_after_gate_closes(self):
        pack_id, package = self._first_pack()
        with patch.dict(os.environ, {"STARS_PAYMENTS_OPEN": "1"}):
            self.bot._handler("callback", "payment_callback")(_callback(f"pay_{pack_id}"))
        self.assertEqual(len(self.bot.invoices), 1)

        query = _pre_checkout(
            f"credits_{package.credits}_{UID}",
            amount=package.stars,
        )
        with patch.dict(os.environ, {"STARS_PAYMENTS_OPEN": "0"}):
            self.bot._handler("pre_checkout", "pre_checkout")(query)

        self.assertFalse(self._answer()["ok"])
        self.assertIn("closed", self._answer()["error_message"].lower())

    def test_open_gate_allows_exact_credit_precheckout(self):
        _pack_id, package = self._first_pack()
        query = _pre_checkout(f"credits_{package.credits}_{UID}", amount=package.stars)

        with patch.dict(os.environ, {"STARS_PAYMENTS_OPEN": "1"}):
            self.bot._handler("pre_checkout", "pre_checkout")(query)

        self.assertTrue(self._answer()["ok"])

    def test_open_gate_still_validates_precheckout_recipient_and_price(self):
        _pack_id, package = self._first_pack()
        wrong_uid = _pre_checkout(
            f"credits_{package.credits}_99999",
            uid=UID,
            amount=package.stars,
        )
        wrong_price = _pre_checkout(
            f"credits_{package.credits}_{UID}",
            amount=package.stars + 1,
        )

        with patch.dict(os.environ, {"STARS_PAYMENTS_OPEN": "1"}):
            self.bot._handler("pre_checkout", "pre_checkout")(wrong_uid)
            self.assertFalse(self._answer()["ok"])
            self.bot._handler("pre_checkout", "pre_checkout")(wrong_price)
            self.assertFalse(self._answer()["ok"])

    def test_successful_payment_callback_is_not_dropped_when_gate_closed(self):
        payment = SimpleNamespace(
            invoice_payload=f"vip_monthly_{UID}",
            telegram_payment_charge_id="already-charged-stars-123",
            currency=TELEGRAM_STARS_CURRENCY,
            total_amount=VIP_MONTHLY_STARS,
        )
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=UID),
            chat=SimpleNamespace(id=CHAT_ID),
            successful_payment=payment,
        )
        duplicate = {"status": "duplicate"}

        with patch.dict(os.environ, {"STARS_PAYMENTS_OPEN": "0"}):
            with patch.object(
                payment_handler.stars_payment_authority,
                "record_vip_subscription_payment",
                return_value=duplicate,
            ) as record:
                self.bot._handler("message", "successful_payment")(message)

        record.assert_called_once()
        self.assertTrue(any("כבר עובד" in str(m) for m in self.bot.messages))


if __name__ == "__main__":
    unittest.main()
