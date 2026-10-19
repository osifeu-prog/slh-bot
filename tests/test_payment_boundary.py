"""Regression coverage for the Telegram Stars payment boundary."""

from core import stars_payment_authority
from handlers.payment_handler import STARS_PACKS, _resolve_stars_package


def test_canonical_packages_resolve_only_at_exact_stars_price():
    assert STARS_PACKS
    for pack_id, package in STARS_PACKS.items():
        resolved = _resolve_stars_package(package.credits, package.stars)
        assert resolved is not None
        assert resolved[0] == pack_id
        assert resolved[1] == package.stars
        assert resolved[2] == package.credits
        assert resolved[3] == package.label


def test_wrong_price_and_unknown_package_values_rejected():
    assert _resolve_stars_package(100, 99) is None
    assert _resolve_stars_package(500, 500) is None
    assert _resolve_stars_package(1000, 801) is None
    assert _resolve_stars_package(9999, 9999) is None
    assert _resolve_stars_package("abc", 100) is None
    assert _resolve_stars_package(100, "abc") is None


def test_payment_authority_rejects_non_xtr_before_economy():
    try:
        stars_payment_authority.record_stars_payment(
            uid="test-user",
            credits=100,
            stars_paid=100,
            currency="USD",
            telegram_payment_charge_id="boundary-test-usd",
        )
    except ValueError as exc:
        assert str(exc) == "INVALID_PAYMENT_CURRENCY"
    else:
        raise AssertionError("non-XTR authority rejection")


def test_payment_authority_delegates_valid_xtr_without_db_side_effects(monkeypatch):
    # Revenue persistence is mocked here so this unit test remains side-effect free.
    called = {}

    def fake_record(**kwargs):
        called.update(kwargs)
        return {
            "status": "applied",
            "uid": kwargs["uid"],
            "credits": 100,
            "charge_id": kwargs["telegram_payment_charge_id"],
        }

    monkeypatch.setattr(
        stars_payment_authority.economy_service,
        "record_stars_payment",
        fake_record,
    )
    monkeypatch.setattr(
        stars_payment_authority,
        "_record_revenue",
        lambda **kwargs: None,
    )

    result = stars_payment_authority.record_stars_payment(
        uid="test-user",
        credits=100,
        stars_paid=100,
        currency="XTR",
        telegram_payment_charge_id="boundary-test-xtr",
    )

    assert called["currency"] == "XTR"
    assert called["uid"] == "test-user"
    assert called["credits"] == 100
    assert result["status"] == "applied"



def test_commerce_status_report_is_read_only_and_separates_payment_rails():
    import copy
    from handlers.payment_handler import _format_commerce_status

    db = {
        "products": {"esp32_pro": {"inventory": 2}},
        "star_item_orders": {
            "stars:done": {"status": "FULFILLED"},
            "stars:recovery": {"status": "RECOVERABLE"},
        },
        "card_orders": {"card:pending": {"status": "PAID"}},
        "revenue_ledger": [
            {"reference": "xtr-1", "currency": "XTR", "amount": 25},
            {"reference": "ils-1", "currency": "ILS", "amount": 199.5},
            {"reference": "", "currency": "ILS", "amount": 999},
            {"reference": "bad", "currency": "XTR", "amount": float("nan")},
        ],
    }
    before = copy.deepcopy(db)

    report = _format_commerce_status(
        db=db,
        stars_prices={"emoji_bitcoin": 25, "course_algo_trading": 150},
        stars_token_configured=True,
        card_status={"enabled": False, "configured": False},
        card_items=[],
        ton_deposits_open=False,
        bnb_deposits_open=False,
    )

    assert "2 מוצר/ים מתומחרים ב-Stars" in report
    assert "emoji_bitcoin: 25⭐" in report
    assert "BLOCKED" in report
    assert "חסרים פרטי ספק" in report
    assert "TON: NOT IMPLEMENTED" in report
    assert "BNB: NOT IMPLEMENTED" in report
    assert "שער הפקדות TON בפועל: CLOSED" in report
    assert "שער הפקדות BNB בפועל: CLOSED" in report
    assert "Stars: 2 הזמנות · 1 סופקו · 1 ממתינות/דורשות התאוששות" in report
    assert "Cards: 1 הזמנות · 0 סופקו · 1 ממתינות/דורשות התאוששות" in report
    assert "XTR (Telegram Stars, לא שקלים): 25" in report
    assert "ILS (ברוטו שנרשם, לא אישור העברה בנקאית): 199.50 ₪" in report
    assert "לא יצר חשבונית/הזמנה" in report
    assert db == before


def test_commerce_status_marks_card_checkout_ready_only_with_stock():
    from handlers.payment_handler import _format_commerce_status

    report = _format_commerce_status(
        db={"products": {"esp32_pro": {"inventory": 3}}},
        stars_prices={},
        stars_token_configured=True,
        card_status={"enabled": True, "configured": True},
        card_items=[
            {"id": "esp32_pro", "name": "ESP32 Pro", "price_ils": 299.0},
            {"id": "esp32_standard", "name": "ESP32 Standard", "price_ils": 199.0},
        ],
        ton_deposits_open=False,
        bnb_deposits_open=False,
    )

    assert "READY לכאורה — 1 מוצר/ים מתומחרים ובעלי מלאי" in report
    assert "ESP32 Pro: 299.00 ₪" in report
    assert "מוצרים ללא מלאי תקין: 1" in report


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__]))
