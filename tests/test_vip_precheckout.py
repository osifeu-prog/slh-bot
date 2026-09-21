import unittest


class FakeBot:
    def __init__(self):
        self.pre_checkout_handlers = []
        self.answers = []

    def message_handler(self, **_kwargs):
        return lambda fn: fn

    def callback_query_handler(self, **_kwargs):
        return lambda fn: fn

    def pre_checkout_query_handler(self, **_kwargs):
        def decorator(fn):
            self.pre_checkout_handlers.append(fn)
            return fn
        return decorator

    def answer_pre_checkout_query(self, query_id, ok, error_message=None):
        self.answers.append({
            "query_id": query_id,
            "ok": ok,
            "error_message": error_message,
        })


class User:
    def __init__(self, user_id):
        self.id = user_id


class Query:
    def __init__(self, user_id, payload, total_amount, currency="XTR"):
        self.id = "q-1"
        self.from_user = User(user_id)
        self.invoice_payload = payload
        self.total_amount = total_amount
        self.currency = currency


class VIPPreCheckoutTests(unittest.TestCase):
    def _handler(self):
        from handlers.payment_handler import register_payment_handlers

        bot = FakeBot()
        register_payment_handlers(bot)
        self.assertEqual(len(bot.pre_checkout_handlers), 1)
        return bot, bot.pre_checkout_handlers[0]

    def test_vip_exact_price_is_accepted(self):
        bot, handler = self._handler()
        handler(Query(123, "vip_monthly_123", 499, "XTR"))
        self.assertEqual(bot.answers[0]["ok"], True)

    def test_vip_wrong_price_is_rejected(self):
        bot, handler = self._handler()
        handler(Query(123, "vip_monthly_123", 500, "XTR"))
        self.assertEqual(bot.answers[0]["ok"], False)

    def test_vip_wrong_currency_is_rejected(self):
        bot, handler = self._handler()
        handler(Query(123, "vip_monthly_123", 499, "USD"))
        self.assertEqual(bot.answers[0]["ok"], False)

    def test_vip_wrong_recipient_is_rejected(self):
        bot, handler = self._handler()
        handler(Query(123, "vip_monthly_456", 499, "XTR"))
        self.assertEqual(bot.answers[0]["ok"], False)


if __name__ == "__main__":
    unittest.main()
