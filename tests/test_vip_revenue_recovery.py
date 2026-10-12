import unittest
from unittest.mock import patch

from core import revenue_ledger
from core.stars_payment_authority import (
    VIP_MONTHLY_STARS,
    record_vip_subscription_payment,
)


class VIPRevenueRecoveryTests(unittest.TestCase):
    @staticmethod
    def _atomic_update_for(db):
        return lambda mutate: mutate(db)

    def test_retry_recovers_transient_revenue_write_failure_once(self):
        db = {
            "users": {"1": {}},
            "vip_subscriptions": {},
            "revenue_ledger": [],
        }
        fulfillment = {
            "status": "completed",
            "launch_offer_qualified": False,
            "bundle": {"status": "completed"},
        }
        original_record = revenue_ledger.record
        attempts = {"count": 0}

        def fail_once_then_record(**kwargs):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("simulated ledger outage")
            return original_record(**kwargs)

        with patch(
            "core.stars_payment_authority.state_manager.atomic_update",
            side_effect=self._atomic_update_for(db),
        ), patch(
            "core.stars_payment_authority.revenue_ledger.record",
            side_effect=fail_once_then_record,
        ), patch(
            "core.stars_payment_authority.apply_vip_benefits",
            return_value=fulfillment,
        ) as apply:
            with self.assertRaisesRegex(RuntimeError, "simulated ledger outage"):
                record_vip_subscription_payment(
                    uid="1",
                    stars_paid=VIP_MONTHLY_STARS,
                    charge_id="charge-recovery-test",
                    now=1000,
                )

            self.assertEqual(
                db["vip_subscriptions"]["charge-recovery-test"]["fulfillment_status"],
                "pending",
            )
            second = record_vip_subscription_payment(
                uid="1",
                stars_paid=VIP_MONTHLY_STARS,
                charge_id="charge-recovery-test",
                now=2000,
            )
            third = record_vip_subscription_payment(
                uid="1",
                stars_paid=VIP_MONTHLY_STARS,
                charge_id="charge-recovery-test",
                now=3000,
            )

        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(third["status"], "duplicate")
        self.assertEqual(third["fulfillment_status"], "completed")
        self.assertEqual(attempts["count"], 3)
        self.assertEqual(len(db["revenue_ledger"]), 1)
        event = db["revenue_ledger"][0]
        self.assertEqual(event["source"], "telegram_stars_subscription")
        self.assertEqual(event["reference"], "charge-recovery-test")
        self.assertEqual(event["currency"], "XTR")
        self.assertEqual(event["amount"], float(VIP_MONTHLY_STARS))
        self.assertEqual(event["uid"], "1")
        self.assertEqual(
            db["vip_subscriptions"]["charge-recovery-test"]["expires_at"],
            1000 + 2592000,
        )
        apply.assert_called_once()

    def test_completed_replay_repairs_missing_revenue_without_refilling(self):
        charge_id = "charge-completed-recovery-test"
        db = {
            "users": {"1": {"vip_access_until": 1000 + 2592000}},
            "vip_subscriptions": {
                charge_id: {
                    "charge_id": charge_id,
                    "uid": "1",
                    "stars_paid": VIP_MONTHLY_STARS,
                    "started_at": 1000,
                    "expires_at": 1000 + 2592000,
                    "status": "ACTIVE",
                    "launch_offer_qualified": False,
                    "fulfillment_status": "completed",
                    "bundle": {"status": "completed"},
                }
            },
            "revenue_ledger": [],
        }

        with patch(
            "core.stars_payment_authority.state_manager.atomic_update",
            side_effect=self._atomic_update_for(db),
        ), patch(
            "core.stars_payment_authority.apply_vip_benefits"
        ) as apply:
            result = record_vip_subscription_payment(
                uid="1",
                stars_paid=VIP_MONTHLY_STARS,
                charge_id=charge_id,
                now=2000,
            )

        self.assertEqual(result["status"], "duplicate")
        self.assertEqual(result["fulfillment_status"], "completed")
        self.assertEqual(len(db["revenue_ledger"]), 1)
        self.assertEqual(db["revenue_ledger"][0]["reference"], charge_id)
        self.assertEqual(db["revenue_ledger"][0]["amount"], float(VIP_MONTHLY_STARS))
        apply.assert_not_called()

    def test_charge_reference_cannot_be_replayed_for_another_user_or_amount(self):
        charge_id = "charge-conflict-test"
        db = {
            "users": {"1": {}, "2": {}},
            "vip_subscriptions": {
                charge_id: {
                    "charge_id": charge_id,
                    "uid": "1",
                    "stars_paid": VIP_MONTHLY_STARS,
                    "fulfillment_status": "completed",
                    "launch_offer_qualified": False,
                }
            },
            "revenue_ledger": [],
        }

        with patch(
            "core.stars_payment_authority.state_manager.atomic_update",
            side_effect=self._atomic_update_for(db),
        ), patch(
            "core.stars_payment_authority._record_revenue"
        ) as revenue, patch(
            "core.stars_payment_authority.apply_vip_benefits"
        ) as apply:
            with self.assertRaisesRegex(ValueError, "VIP_CHARGE_UID_CONFLICT"):
                record_vip_subscription_payment(
                    uid="2",
                    stars_paid=VIP_MONTHLY_STARS,
                    charge_id=charge_id,
                    now=2000,
                )
            with self.assertRaisesRegex(ValueError, "VIP_CHARGE_AMOUNT_CONFLICT"):
                record_vip_subscription_payment(
                    uid="1",
                    stars_paid=VIP_MONTHLY_STARS + 1,
                    charge_id=charge_id,
                    now=2000,
                )

        revenue.assert_not_called()
        apply.assert_not_called()


if __name__ == "__main__":
    unittest.main()
