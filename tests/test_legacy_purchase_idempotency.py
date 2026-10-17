import copy
import unittest
from unittest.mock import patch

from core import economy_service


UID = "12345"
OTHER_UID = "67890"
REFERRER_UID = "24680"
TREASURY_UID = "SLH_TREASURY"


class LegacyPurchaseBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.db = {
            "users": {
                UID: {"wallet": {"credits": 100.0}},
                OTHER_UID: {"wallet": {"credits": 75.0}},
                REFERRER_UID: {"wallet": {"credits": 10.0}},
                TREASURY_UID: {"wallet": {"credits": 1000.0}},
            },
            "ledger": [],
        }
        self.atomic_patch = patch.object(
            economy_service.state_manager,
            "atomic_update",
            side_effect=lambda mutate: mutate(self.db),
        )
        self.atomic_patch.start()
        self.addCleanup(self.atomic_patch.stop)

    def _purchase(self, uid=UID, item="ask_credit", price=10.0, key="request-1", source="telegram_buy"):
        return economy_service.purchase_item(
            uid=uid,
            item=item,
            price=price,
            meta={
                "source": source,
                "idempotency_key": key,
                "item_id": item,
            },
        )

    def test_exact_replay_debits_and_grants_only_once(self):
        first = self._purchase()
        self.assertEqual(first["credits"], 90.0)
        self.assertEqual(self.db["users"][UID]["ask_credits"], 1)
        self.assertEqual(len(self.db["ledger"]), 1)
        before_replay = copy.deepcopy(self.db)

        second = self._purchase()

        self.assertTrue(second["duplicate"])
        self.assertEqual(second["credits"], 90.0)
        self.assertEqual(self.db, before_replay)

    def test_same_key_with_another_uid_is_a_conflict(self):
        self._purchase()
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_CONFLICT"):
            self._purchase(uid=OTHER_UID)

        self.assertEqual(self.db, before)

    def test_same_key_with_another_item_is_a_conflict(self):
        self._purchase()
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_CONFLICT"):
            self._purchase(item="premium_agent", price=50.0)

        self.assertEqual(self.db, before)

    def test_same_key_with_another_price_is_a_conflict(self):
        self._purchase()
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_CONFLICT"):
            self._purchase(price=11.0)

        self.assertEqual(self.db, before)

    def test_same_key_with_another_source_is_a_conflict(self):
        self._purchase()
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_CONFLICT"):
            self._purchase(source="different_route")

        self.assertEqual(self.db, before)

    def test_new_purchase_for_frozen_account_fails_without_mutation(self):
        self.db["users"][UID]["frozen"] = True
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "ACCOUNT_FROZEN"):
            self._purchase(key="new-request")

        self.assertEqual(self.db, before)

    def test_exact_replay_after_freeze_is_a_read_only_noop(self):
        self._purchase()
        self.db["users"][UID]["frozen"] = True
        before = copy.deepcopy(self.db)

        result = self._purchase()

        self.assertTrue(result["duplicate"])
        self.assertEqual(self.db, before)

    def test_referral_commission_is_not_issued_twice_on_replay(self):
        self.db["users"][UID]["referral"] = {"referred_by": REFERRER_UID}
        first = self._purchase()
        self.assertEqual(first["commission"], 1.0)
        self.assertEqual(self.db["users"][REFERRER_UID]["wallet"]["credits"], 11.0)
        self.assertEqual(self.db["users"][TREASURY_UID]["wallet"]["credits"], 999.0)
        self.assertEqual(self.db["commissions"][REFERRER_UID], 1.0)
        before_replay = copy.deepcopy(self.db)

        second = self._purchase()

        self.assertTrue(second["duplicate"])
        self.assertEqual(self.db, before_replay)

    def test_missing_idempotency_key_fails_closed(self):
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_REQUIRED"):
            economy_service.purchase_item(
                uid=UID,
                item="ask_credit",
                price=10,
                meta={"source": "telegram_buy"},
            )

        self.assertEqual(self.db, before)

    def test_insufficient_credits_fails_without_mutation(self):
        self.db["users"][UID]["wallet"]["credits"] = 0.0
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_CREDITS"):
            self._purchase(key="insufficient-request")

        self.assertEqual(self.db, before)

    def test_unknown_item_fails_before_mutation(self):
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "UNKNOWN_ITEM"):
            self._purchase(item="unrecognized", key="unknown-request")

        self.assertEqual(self.db, before)


if __name__ == "__main__":
    unittest.main()
