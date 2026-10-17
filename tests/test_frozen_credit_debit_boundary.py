import copy
import unittest
from unittest.mock import patch

from core import economy_service, staking_service


def _db(*, frozen=True):
    return {
        "users": {
            "u1": {
                "frozen": frozen,
                "wallet": {"credits": 100.0, "staked": 0.0},
            },
            "SLH_TREASURY": {"wallet": {"credits": 0.0}},
        },
        "ledger": [],
        "stake_positions": {},
        "staking_requests": {},
        "staking_unstake_requests": {},
    }


class FrozenCreditsDebitBoundaryTests(unittest.TestCase):
    def _atomic(self, target, db):
        return patch.object(
            target.state_manager,
            "atomic_update",
            side_effect=lambda mutate: mutate(db),
        )

    def test_frozen_account_cannot_make_generic_negative_credits_transaction(self):
        db = _db(frozen=True)
        before = copy.deepcopy(db)

        with self._atomic(economy_service, db):
            with self.assertRaisesRegex(ValueError, "ACCOUNT_FROZEN"):
                economy_service.record_transaction(
                    "u1",
                    -5.0,
                    reason="arcade:entry",
                    meta={"source": "unit_test", "idempotency_key": "frozen-legacy-purchase"},
                )

        self.assertEqual(db, before)

    def test_non_frozen_account_can_make_generic_negative_credits_transaction(self):
        db = _db(frozen=False)

        with self._atomic(economy_service, db):
            result = economy_service.record_transaction(
                "u1",
                -5.0,
                reason="arcade:entry",
                meta={"source": "unit_test"},
            )

        self.assertEqual(result, 95.0)
        self.assertEqual(db["users"]["u1"]["wallet"]["credits"], 95.0)
        self.assertEqual(len(db["ledger"]), 1)

    def test_frozen_account_cannot_use_legacy_purchase_item_authority(self):
        db = _db(frozen=True)
        before = copy.deepcopy(db)

        with self._atomic(economy_service, db):
            with self.assertRaisesRegex(ValueError, "ACCOUNT_FROZEN"):
                economy_service.purchase_item(
                    uid="u1",
                    item="ask_credit",
                    price=10,
                    meta={"source": "unit_test"},
                )

        self.assertEqual(db, before)
        self.assertNotIn("ask_credits", db["users"]["u1"])
        self.assertNotIn("premium", db["users"]["u1"])

    def test_frozen_account_cannot_create_new_staking_position(self):
        db = _db(frozen=True)
        before = copy.deepcopy(db)

        with self._atomic(staking_service, db):
            with self.assertRaisesRegex(ValueError, "ACCOUNT_FROZEN"):
                staking_service.stake_locked(
                    "u1", 10, lock_days=30, request_id="fresh-stake",
                    meta={"source": "unit_test"},
                )

        self.assertEqual(db, before)

    def test_frozen_account_can_retry_already_recorded_stake_without_mutation(self):
        db = _db(frozen=False)
        with self._atomic(staking_service, db):
            first = staking_service.stake_locked(
                "u1", 10, lock_days=30, request_id="existing-stake",
                meta={"source": "unit_test"},
            )
        self.assertEqual(first["status"], "completed")
        db["users"]["u1"]["frozen"] = True
        before_retry = copy.deepcopy(db)

        with self._atomic(staking_service, db):
            replay = staking_service.stake_locked(
                "u1", 10, lock_days=30, request_id="existing-stake",
                meta={"source": "unit_test"},
            )

        self.assertEqual(replay["status"], "duplicate")
        self.assertEqual(db, before_retry)


if __name__ == "__main__":
    unittest.main()
