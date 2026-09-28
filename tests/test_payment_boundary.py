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


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__]))
