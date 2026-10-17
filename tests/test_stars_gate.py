import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core import stars_gate
from handlers import payment_handler, stars_store


class FakeBot:
    def __init__(self):
        self.handlers = {}
        self.pre_checkout_calls = []
        self.callback_calls = []
        self.sent_invoices = []

    def _decorator(self, *args, **kwargs):
        def register(fn):
            self.handlers[fn.__name__] = fn
            return fn
        return register

    message_handler = _decorator
    callback_query_handler = _decorator
    pre_checkout_query_handler = _decorator

    def answer_pre_checkout_query(self, *args, **kwargs):
        self.pre_checkout_calls.append((args, kwargs))

    def answer_callback_query(self, *args, **kwargs):
        self.callback_calls.append((args, kwargs))

    def send_invoice(self, *args, **kwargs):
        self.sent_invoices.append((args, kwargs))

    def send_message(self, *args, **kwargs):
        pass

    def reply_to(self, *args, **kwargs):
        pass

    def edit_message_text(self, *args, **kwargs):
        pass

    def create_invoice_link(self, *args, **kwargs):
        raise AssertionError("invoice link must not be created while gate is closed")


def test_stars_gate_defaults_closed(monkeypatch):
    monkeypatch.delenv("STARS_PAYMENTS_OPEN", raising=False)
    assert stars_gate.stars_payments_open() is False


@pytest.mark.parametrize("value", ["", "0", "false", "yes", " 1 "])
def test_stars_gate_only_opens_for_exact_one(monkeypatch, value):
    monkeypatch.setenv("STARS_PAYMENTS_OPEN", value)
    assert stars_gate.stars_payments_open() is (value.strip() == "1")


def test_pay_menu_does_not_load_account_or_offer_checkout_when_closed(monkeypatch):
    monkeypatch.setenv("STARS_PAYMENTS_OPEN", "0")
    bot = FakeBot()
    with patch.object(payment_handler.state_manager, "load_db", side_effect=AssertionError("must not load")):
        payment_handler._send_pay_menu(bot, 42, "100")
    # FakeBot tracks messages indirectly; the important boundary is that no
    # account lookup and no invoice creation is reached when closed.
    assert bot.sent_invoices == []


def test_vip_invoice_link_is_not_created_when_closed(monkeypatch):
    monkeypatch.setenv("STARS_PAYMENTS_OPEN", "0")
    bot = FakeBot()
    with pytest.raises(RuntimeError, match="STARS_PAYMENTS_CLOSED"):
        payment_handler._create_vip_invoice_link(bot, "100")
    assert bot.sent_invoices == []


def test_pre_checkout_rejects_new_charge_when_closed(monkeypatch):
    monkeypatch.setenv("STARS_PAYMENTS_OPEN", "0")
    bot = FakeBot()
    payment_handler.register_payment_handlers(bot)
    query = SimpleNamespace(id="pre-1", invoice_payload="credits_100_100")
    bot.handlers["pre_checkout"](query)

    assert bot.pre_checkout_calls == [(
        ("pre-1",),
        {
            "ok": False,
            "error_message": "SLH Stars payments are temporarily closed.",
        },
    )]


def test_credit_invoice_callback_does_not_create_invoice_when_closed(monkeypatch):
    monkeypatch.setenv("STARS_PAYMENTS_OPEN", "0")
    bot = FakeBot()
    payment_handler.register_payment_handlers(bot)
    call = SimpleNamespace(id="callback-1", data="pay_pack")
    bot.handlers["payment_callback"](call)

    assert bot.sent_invoices == []
    assert bot.callback_calls
    assert bot.callback_calls[0][0][0] == "callback-1"
    assert "סגורים" in bot.callback_calls[0][0][1]
    assert bot.callback_calls[0][1]["show_alert"] is True


def test_store_stars_command_does_not_build_invoice_when_closed(monkeypatch):
    monkeypatch.setenv("STARS_PAYMENTS_OPEN", "0")
    bot = FakeBot()
    stars_store.register(bot)
    message = SimpleNamespace(
        text="/buystars course_ethereum",
        from_user=SimpleNamespace(id=100),
        chat=SimpleNamespace(id=100),
    )
    with patch.object(stars_store, "load_items", side_effect=AssertionError("must not load catalog")):
        bot.handlers["buystars"](message)
    assert bot.sent_invoices == []


def test_gate_closure_does_not_add_a_guard_to_confirmed_payment_callback():
    # Regression contract: successful_payment must continue to record/recover
    # charges confirmed by Telegram before a gate changed. The checkout gate
    # is enforced before invoice creation and at pre-checkout instead.
    import inspect
    source = inspect.getsource(payment_handler.register_payment_handlers)
    assert "def successful_payment(m):" in source
    segment = source.split("def successful_payment(m):", 1)[1].split("def cardpay_command", 1)[0]
    assert "STARS_PAYMENTS_CLOSED" not in segment
