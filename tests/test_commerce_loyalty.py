import copy
from unittest.mock import patch

from core import commerce_loyalty


def _db():
    return {
        "users": {
            "100": {"wallet": {"credits": 0}, "acquisition_channel": "whatsapp"},
            "200": {"wallet": {"credits": 0}},
            "300": {"wallet": {"credits": 0}, "referral": {"referred_by": "200"}},
        },
        "ledger": [],
    }


def _atomic(db):
    return patch(
        "core.commerce_loyalty.state_manager.atomic_update",
        side_effect=lambda mutator: mutator(db),
    )


def test_whatsapp_bundle_cashback_is_90_credits_and_idempotent():
    db = _db()
    with _atomic(db):
        first = commerce_loyalty.grant_whatsapp_cashback(
            "100", "stars:charge-bundle", 899, "XTR", sku="slh_investor_bundle"
        )
        second = commerce_loyalty.grant_whatsapp_cashback(
            "100", "stars:charge-bundle", 899, "XTR", sku="slh_investor_bundle"
        )

    assert first["status"] == "APPLIED"
    assert second["status"] == "DUPLICATE"
    assert db["users"]["100"]["wallet"]["credits"] == 90.0
    assert len([x for x in db["ledger"] if x.get("reason") == "whatsapp:cashback"]) == 1


def test_non_whatsapp_user_does_not_receive_cashback():
    db = _db()
    with _atomic(db):
        result = commerce_loyalty.grant_whatsapp_cashback(
            "200", "stars:charge-1", 899, "XTR", sku="slh_investor_bundle"
        )

    assert result["status"] == "NOT_ELIGIBLE"
    assert db["users"]["200"]["wallet"]["credits"] == 0
    assert db["ledger"] == []


def test_test_skus_do_not_receive_cashback():
    db = _db()
    with _atomic(db):
        result = commerce_loyalty.grant_whatsapp_cashback(
            "100", "purchase:test-bill", 5, "CREDITS", sku="test_bill"
        )
    assert result["status"] == "INELIGIBLE_TEST_SKU"
    assert db["users"]["100"]["wallet"]["credits"] == 0


def test_vip_referral_awards_new_buyer_25_and_referrer_10_percent_once_per_charge():
    db = _db()
    with _atomic(db):
        first = commerce_loyalty.settle_referred_vip_purchase("300", "vip-charge-1", 499)
        replay = commerce_loyalty.settle_referred_vip_purchase("300", "vip-charge-1", 499)
        renewal = commerce_loyalty.settle_referred_vip_purchase("300", "vip-charge-2", 499)

    assert first["status"] == "APPLIED"
    assert replay["status"] == "DUPLICATE"
    assert renewal["status"] == "APPLIED"
    assert db["users"]["300"]["wallet"]["credits"] == 25.0
    assert db["users"]["200"]["wallet"]["credits"] == 100.0
    assert len([x for x in db["ledger"] if x.get("reason") == "vip:referral_new_buyer_bonus"]) == 1
    assert len([x for x in db["ledger"] if x.get("reason") == "vip:referral_purchase_commission"]) == 2


def test_cashback_for_credits_purchase_uses_ten_percent():
    db = _db()
    with _atomic(db):
        result = commerce_loyalty.grant_whatsapp_cashback(
            "100", "purchase:esp32-pro", 888, "CREDITS", sku="esp32_pro"
        )
    assert result["status"] == "APPLIED"
    assert result["credits"] == "88.80000000"
    assert db["users"]["100"]["wallet"]["credits"] == 88.8
