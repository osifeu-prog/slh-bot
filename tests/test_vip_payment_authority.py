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


if __name__ == "__main__":
    unittest.main()
