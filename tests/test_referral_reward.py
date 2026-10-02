import unittest
from unittest import mock

import state_manager
from core import referral_reward


def make_db(count, extra=None):
    db = {"users": {"1": {"referral": {"count": count}}}}
    if extra:
        db.update(extra)
    return db


class ReferralRewardTests(unittest.TestCase):
    def award(self, db, uid="1", now=1000):
        def atomic(fn):
            return fn(db)

        with mock.patch.object(state_manager, "atomic_update", atomic):
            with mock.patch.object(state_manager, "load_db", lambda: db):
                return referral_reward.maybe_award(uid, now=now)

    def test_successful_referral_reward_policy(self):
        with mock.patch.object(referral_reward, "grant") as grant, mock.patch.object(
            referral_reward, "maybe_award", return_value=None
        ):
            grant.side_effect = [{"points": 10}, {"credits": 0.9}]
            result = referral_reward.settle_successful_referral("1", "2")

        assert result["points"]["points"] == 10
        assert result["credits"]["credits"] == 0.9
        assert grant.call_args_list[0].kwargs["idempotency_key"] == "ref:2"
        assert grant.call_args_list[1].kwargs["idempotency_key"] == "referral-credit:2"

    def test_grants_vip_at_five(self):
        db = make_db(5)
        self.assertIsNotNone(self.award(db))
        user = db["users"]["1"]
        self.assertIn("vip_access", user["permissions"])
        self.assertGreater(user["vip_access_until"], 1000)

    def test_below_threshold_grants_nothing(self):
        db = make_db(4)
        self.assertIsNone(self.award(db))
        self.assertNotIn("vip_access_until", db["users"]["1"])

    def test_not_granted_twice(self):
        db = make_db(5)
        self.assertIsNotNone(self.award(db))
        self.assertIsNone(self.award(db))

    def test_extends_existing_vip(self):
        db = make_db(5)
        db["users"]["1"]["vip_access_until"] = 5000
        self.assertIsNotNone(self.award(db))
        self.assertGreater(db["users"]["1"]["vip_access_until"], 5000)

    def test_stops_after_max_awards(self):
        taken = {str(i): {} for i in range(10, 20)}
        db = make_db(5, {"referral_vip_awards": taken})
        self.assertIsNone(self.award(db))

    def test_closed_offer_grants_nothing(self):
        db = make_db(5)
        self.assertIsNone(self.award(db, now=referral_reward.OFFER_ENDS_AT + 1))


if __name__ == "__main__":
    unittest.main()
