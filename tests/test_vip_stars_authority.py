import unittest
from unittest.mock import patch


class VIPStarsAuthorityTests(unittest.TestCase):
    def test_vip_charge_is_idempotent_and_reconciles_revenue(self):
        from core import stars_payment_authority

        db = {"users": {}}

        def atomic_update(fn):
            return fn(db)

        with patch.object(stars_payment_authority.state_manager, "atomic_update", side_effect=atomic_update),              patch.object(stars_payment_authority.revenue_ledger, "record") as revenue:
            first = stars_payment_authority.record_vip_subscription_payment(
                uid="100",
                stars_paid=499,
                charge_id="vip-charge-1",
                now=1000,
            )
            second = stars_payment_authority.record_vip_subscription_payment(
                uid="100",
                stars_paid=499,
                charge_id="vip-charge-1",
                now=1000,
            )

        self.assertEqual(first["status"], "applied")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(db["users"]["100"]["vip_access_until"], 1000 + 2592000)
        self.assertEqual(len(db["vip_subscriptions"]), 1)
        self.assertEqual(revenue.call_count, 1)

    def test_vip_wrong_amount_is_rejected_before_state_change(self):
        from core import stars_payment_authority

        db = {"users": {}}

        def atomic_update(fn):
            return fn(db)

        with patch.object(stars_payment_authority.state_manager, "atomic_update", side_effect=atomic_update):
            with self.assertRaises(ValueError):
                stars_payment_authority.record_vip_subscription_payment(
                    uid="100",
                    stars_paid=500,
                    charge_id="vip-bad",
                    now=1000,
                )

        self.assertEqual(db["users"], {})


if __name__ == "__main__":
    unittest.main()
