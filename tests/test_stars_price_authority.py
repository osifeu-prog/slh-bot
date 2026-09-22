from core.stars_price_authority import (
    CREDIT_PACKS,
    CREDIT_PACKS_BY_ID,
    TELEGRAM_STARS_CURRENCY,
    VIP_MONTHLY_STARS,
    VIP_SUBSCRIPTION_PERIOD,
    resolve_credit_pack,
)


def test_credit_pack_catalog_is_canonical():
    assert TELEGRAM_STARS_CURRENCY == "XTR"
    assert VIP_MONTHLY_STARS == 499
    assert VIP_SUBSCRIPTION_PERIOD == 2592000

    assert [(p.stars, p.credits) for p in CREDIT_PACKS] == [
        (100, 100),
        (500, 550),
        (1000, 1200),
    ]
    assert set(CREDIT_PACKS_BY_ID) == {"100credits", "500credits", "1000credits"}


def test_credit_pack_resolution_requires_exact_stars_and_credits():
    assert resolve_credit_pack(100, 100).pack_id == "100credits"
    assert resolve_credit_pack(550, 500).pack_id == "500credits"
    assert resolve_credit_pack(1200, 1000).pack_id == "1000credits"
    assert resolve_credit_pack(500, 500) is None
    assert resolve_credit_pack(1200, 500) is None


def test_button_text_matches_catalog():
    assert CREDIT_PACKS_BY_ID["500credits"].button_text == "⭐ 500 Stars → 550 Credits (בונוס 10%)"
    assert CREDIT_PACKS_BY_ID["1000credits"].button_text == "⭐ 1000 Stars → 1200 Credits (בונוס 20%)"
