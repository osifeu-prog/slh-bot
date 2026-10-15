import unittest
from unittest.mock import patch


class VIPPaymentAuthorityTests(unittest.TestCase):
    def test_first_payment_before_deadline_qualifies_and_fulfills_bundle(self):
        import copy

        import core.stars_payment_authority as authority

        db = {"users": {"1": {"wallet": {"credits": 0}, "permissions": []}}, "vip_subscriptions": {}}

        def atomic_update(fn):
            value = fn(db)
            return copy.deepcopy(value)

        bundle = {
            "status": "completed",
            "launch_offer_qualified": True,
            "steps": {"agent_os": True, "emoji_vip": True, "credits": True},
        }

        with patch.object(authority.state_manager, "atomic_update", side_effect=atomic_update),              patch.object(authority.revenue_ledger, "record"),              patch.object(authority, "apply_vip_benefits", return_value=bundle):
            result = authority.record_vip_subscription_payment(
                uid="1",
                stars_paid=499,
                charge_id="charge-1",
                now=1793473199,
            )

        record = db["vip_subscriptions"]["charge-1"]
        self.assertTrue(record["launch_offer_qualified"])
        self.assertEqual(record["fulfillment_status"], "completed")
        self.assertTrue(db["users"]["1"]["vip_launch_offer_qualified"])
        self.assertEqual(result["launch_offer_qualified"], True)

    def test_duplicate_payment_replays_fulfillment_without_new_subscription(self):
        import copy

        import core.stars_payment_authority as authority

        db = {
            "users": {
                "1": {
                    "wallet": {"credits": 0},
                    "permissions": ["vip_access"],
                    "vip_launch_offer_qualified": True,
                }
            },
            "vip_subscriptions": {
                "charge-1": {
                    "charge_id": "charge-1",
                    "uid": "1",
                    "stars_paid": 499,
                    "started_at": 1,
                    "expires_at": 2,
                    "status": "ACTIVE",
                    "launch_offer_qualified": True,
                    "fulfillment_status": "completed",
                }
            },
        }

        def atomic_update(fn):
            value = fn(db)
            return copy.deepcopy(value)

        with patch.object(authority.state_manager, "atomic_update", side_effect=atomic_update),              patch.object(authority.revenue_ledger, "record"),              patch.object(
                 authority,
                 "apply_vip_benefits",
                 return_value={"status": "completed", "launch_offer_qualified": True},
             ) as fulfill:
            result = authority.record_vip_subscription_payment(
                uid="1",
                stars_paid=499,
                charge_id="charge-1",
                now=1793473199,
            )

        self.assertEqual(result["status"], "duplicate")
        fulfill.assert_not_called()



    def test_pending_duplicate_retries_revenue_recording(self):
        import copy

        import core.stars_payment_authority as authority

        db = {
            "users": {"1": {"wallet": {"credits": 0}, "permissions": ["vip_access"]}},
            "vip_subscriptions": {
                "charge-pending": {
                    "charge_id": "charge-pending",
                    "uid": "1",
                    "stars_paid": 499,
                    "started_at": 1,
                    "expires_at": 2,
                    "status": "ACTIVE",
                    "launch_offer_qualified": False,
                    "fulfillment_status": "pending",
                }
            },
        }

        def atomic_update(fn):
            return copy.deepcopy(fn(db))

        bundle = {"status": "completed", "launch_offer_qualified": False}
        with (
            patch.object(authority.state_manager, "atomic_update", side_effect=atomic_update),
            patch.object(authority.revenue_ledger, "record") as record_revenue,
            patch.object(authority, "apply_vip_benefits", return_value=bundle),
        ):
            result = authority.record_vip_subscription_payment(
                uid="1",
                stars_paid=499,
                charge_id="charge-pending",
                now=1793473199,
            )

        record_revenue.assert_not_called()
        self.assertEqual(len(db.get("revenue_ledger", [])), 1)
        self.assertEqual(db["revenue_ledger"][0]["reference"], "charge-pending")
        self.assertEqual(result["status"], "duplicate")
        self.assertEqual(result["fulfillment_status"], "completed")




class VIPAnnualPaymentAuthorityTests(unittest.TestCase):
    def _patch_loyalty(self):
        from core import commerce_loyalty
        return (
            patch.object(commerce_loyalty, "grant_whatsapp_cashback", return_value={"status": "NOT_ELIGIBLE"}),
            patch.object(commerce_loyalty, "settle_referred_vip_purchase", return_value={"status": "NOT_ELIGIBLE"}),
        )

    def test_annual_payment_grants_365_days_without_recurring(self):
        import copy
        import core.stars_payment_authority as authority
        from core.stars_price_authority import VIP_ANNUAL_PERIOD, VIP_ANNUAL_STARS

        now = 1_800_000_000
        db = {"users": {"100": {"wallet": {"credits": 0}, "permissions": []}}, "vip_subscriptions": {}}

        def atomic_update(fn):
            result = fn(db)
            return copy.deepcopy(result)

        cashback, referral = self._patch_loyalty()
        with (
            patch.object(authority.state_manager, "atomic_update", side_effect=atomic_update),
            patch.object(authority, "apply_vip_benefits", return_value={"status": "completed", "launch_offer_qualified": False}),
            cashback,
            referral,
        ):
            result = authority.record_vip_subscription_payment(
                uid="100",
                stars_paid=VIP_ANNUAL_STARS,
                charge_id="annual-charge-1",
                recurring=False,
                first_recurring=False,
                annual=True,
                now=now,
            )

        record = db["vip_subscriptions"]["annual-charge-1"]
        self.assertEqual(result["status"], "applied")
        self.assertTrue(record["annual"])
        self.assertEqual(record["period_months"], 12)
        self.assertFalse(record["recurring"])
        self.assertEqual(record["expires_at"], now + VIP_ANNUAL_PERIOD)
        self.assertEqual(db["users"]["100"]["vip_access_until"], now + VIP_ANNUAL_PERIOD)
        self.assertIn("vip_access", db["users"]["100"]["permissions"])

    def test_annual_replay_does_not_extend_expiry_again(self):
        import copy
        import core.stars_payment_authority as authority
        from core.stars_price_authority import VIP_ANNUAL_PERIOD, VIP_ANNUAL_STARS

        now = 1_800_000_000
        db = {"users": {"100": {"wallet": {"credits": 0}, "permissions": []}}, "vip_subscriptions": {}}

        def atomic_update(fn):
            result = fn(db)
            return copy.deepcopy(result)

        cashback, referral = self._patch_loyalty()
        with (
            patch.object(authority.state_manager, "atomic_update", side_effect=atomic_update),
            patch.object(authority, "apply_vip_benefits", return_value={"status": "completed", "launch_offer_qualified": False}),
            cashback,
            referral,
        ):
            first = authority.record_vip_subscription_payment(
                uid="100", stars_paid=VIP_ANNUAL_STARS, charge_id="annual-charge-replay",
                annual=True, now=now,
            )
            second = authority.record_vip_subscription_payment(
                uid="100", stars_paid=VIP_ANNUAL_STARS, charge_id="annual-charge-replay",
                annual=True, now=now + 300,
            )

        self.assertEqual(first["status"], "applied")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(db["users"]["100"]["vip_access_until"], now + VIP_ANNUAL_PERIOD)
        self.assertEqual(len(db["vip_subscriptions"]), 1)

    def test_annual_checkout_rejects_monthly_price(self):
        import core.stars_payment_authority as authority
        with patch.object(authority.state_manager, "atomic_update") as update:
            with self.assertRaisesRegex(ValueError, "INVALID_VIP_STARS_AMOUNT"):
                authority.record_vip_subscription_payment(
                    uid="100", stars_paid=499, charge_id="wrong-annual-price", annual=True
                )
        update.assert_not_called()


if __name__ == "__main__":
    unittest.main()
