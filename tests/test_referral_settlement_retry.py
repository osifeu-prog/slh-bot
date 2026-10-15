import unittest
from unittest import mock

import state_manager
from core import referral_reward, referral_settlement


class ReferralSettlementRetryTests(unittest.TestCase):
    def setUp(self):
        self.db = {
            "users": {
                "10": {"referral": {"count": 1}},
                "20": {"joined": True, "referral": {"referred_by": "10"}},
            },
            "pending_referrals": {"20": "10"},
        }

        def atomic_update(mutate):
            return mutate(self.db)

        self.atomic_update = atomic_update

    def test_failure_keeps_pending_and_retry_clears_after_success(self):
        settled = {"points": {"points": 10}, "credits": {"credits": 0.9}, "vip": None}
        with mock.patch.object(state_manager, "load_db", lambda: self.db), mock.patch.object(
            state_manager, "atomic_update", self.atomic_update
        ), mock.patch(
            "core.referral_reward.settle_successful_referral",
            side_effect=[RuntimeError("simulated credit-ledger failure"), settled],
        ) as settle:
            with self.assertRaisesRegex(RuntimeError, "simulated credit-ledger failure"):
                referral_settlement.settle_persisted_referral("20")

            self.assertEqual(self.db["pending_referrals"]["20"], "10")
            self.assertEqual(self.db["users"]["20"]["referral"]["referred_by"], "10")

            result = referral_settlement.settle_persisted_referral("20")

        self.assertEqual(result["status"], "SETTLED")
        self.assertEqual(settle.call_count, 2)
        self.assertNotIn("20", self.db["pending_referrals"])
        self.assertEqual(self.db["users"]["10"]["referral"]["count"], 1)

    def test_retries_use_canonical_relationship_not_pending_referrer(self):
        self.db["pending_referrals"]["20"] = "999"
        with mock.patch.object(state_manager, "load_db", lambda: self.db), mock.patch.object(
            state_manager, "atomic_update", self.atomic_update
        ), mock.patch(
            "core.referral_reward.settle_successful_referral",
            return_value={"points": {"points": 10}, "credits": {"credits": 0.9}, "vip": None},
        ) as settle:
            result = referral_settlement.settle_persisted_referral("20")

        self.assertEqual(result["status"], "SETTLED")
        settle.assert_called_once_with("10", "20")
        self.assertEqual(self.db["pending_referrals"]["20"], "999")

    def test_partial_component_retry_uses_stable_keys_without_duplicate_awards(self):
        applied = {}
        fail_credit_once = {"value": True}

        def idempotent_grant(uid, reason, credits=0, points=0, idempotency_key=None):
            if reason == "referral_success_bonus" and fail_credit_once["value"]:
                fail_credit_once["value"] = False
                raise RuntimeError("simulated credit write failure")
            if idempotency_key in applied:
                return {"duplicate": True, "idempotency_key": idempotency_key}
            applied[idempotency_key] = {
                "uid": uid, "reason": reason, "credits": credits, "points": points
            }
            return {"credits": credits, "points": points}

        with mock.patch.object(referral_reward, "grant", side_effect=idempotent_grant), mock.patch.object(
            referral_reward, "maybe_award", return_value=None
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated credit write failure"):
                referral_reward.settle_successful_referral("10", "20")

            # Points were applied before the Credits component failed. Retry and replay
            # must use the same stable keys, so only the missing component is applied.
            referral_reward.settle_successful_referral("10", "20")
            referral_reward.settle_successful_referral("10", "20")

        self.assertEqual(set(applied), {"ref:20", "referral-credit:20"})
        self.assertEqual(applied["ref:20"]["points"], 10)
        self.assertEqual(applied["referral-credit:20"]["credits"], 0.9)

    def test_missing_relationship_does_not_award(self):
        self.db["users"]["20"]["referral"] = {}
        with mock.patch.object(state_manager, "load_db", lambda: self.db), mock.patch.object(
            state_manager, "atomic_update", self.atomic_update
        ), mock.patch("core.referral_reward.settle_successful_referral") as settle:
            result = referral_settlement.settle_persisted_referral("20")

        self.assertEqual(result["status"], "NO_REFERRAL")
        settle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
