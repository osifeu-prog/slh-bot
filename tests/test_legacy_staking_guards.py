import copy
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import state_manager
from core import economy_service, staking_service


UID = "synthetic-owner"
POSITION_ID = "sp_synthetic_100"


def _iso(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _legacy_unstake(amount=100.0, at=1049.0, position_id=None):
    meta = {"source": "test", "command": "unstake"}
    if position_id:
        meta["position_id"] = position_id
    return {
        "time": _iso(at),
        "uid": UID,
        "before": 400.0,
        "amount": amount,
        "after": 400.0 + amount,
        "reason": "staking:unstake",
        "meta": meta,
    }


def _synthetic_db(legacy_row=None):
    position = {
        "id": POSITION_ID,
        "uid": UID,
        "amount": 100.0,
        "status": "locked",
        "created_at": 1000.0,
        "unlocks_at": 0,
    }
    return {
        "users": {UID: {"wallet": {"credits": 500.0, "staked": 300.0}}},
        "stake_positions": {POSITION_ID: position},
        "ledger": [copy.deepcopy(legacy_row)] if legacy_row else [],
        "staking_unstake_requests": {},
    }


def _patch_atomic_db(testcase, db):
    testcase.enterContext(
        patch.object(state_manager, "atomic_update", lambda mutate: mutate(db))
    )
    testcase.enterContext(patch.object(staking_service.time, "time", lambda: 2000.0))


class TestLegacyStakingDisabled(unittest.TestCase):
    def test_stake_credits_is_disabled(self):
        with self.assertRaisesRegex(RuntimeError, "staking_service.stake_locked"):
            economy_service.stake_credits("1", 10)

    def test_unstake_credits_is_disabled(self):
        with self.assertRaisesRegex(RuntimeError, "staking_service.unstake_locked"):
            economy_service.unstake_credits("1", 10)


class TestLegacyStakingGuards(unittest.TestCase):
    def test_same_amount_legacy_unstake_near_creation_blocks_without_mutation(self):
        db = _synthetic_db(legacy_row=_legacy_unstake(amount=100.0, at=1049.0))
        before = copy.deepcopy(db)
        _patch_atomic_db(self, db)

        result = staking_service.unstake_locked(UID, POSITION_ID)

        self.assertEqual(result["status"], "legacy_refund_review_required")
        self.assertEqual(result["code"], "LEGACY_UNSTAKE_AMBIGUITY")
        self.assertEqual(result["evidence"]["ledger_index"], 0)
        self.assertEqual(result["evidence"]["seconds_from_creation"], 49.0)
        self.assertEqual(db, before)

    def test_larger_aggregate_refund_near_creation_is_not_false_matched(self):
        db = _synthetic_db(legacy_row=_legacy_unstake(amount=166.0, at=1049.0))
        _patch_atomic_db(self, db)

        result = staking_service.unstake_locked(UID, POSITION_ID)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["credits"], 600.0)
        self.assertEqual(result["staked"], 200.0)
        self.assertEqual(
            db["ledger"][-1]["meta"]["idempotency_key"],
            f"unstake:{POSITION_ID}",
        )

    def test_same_amount_legacy_unstake_outside_five_minutes_is_not_matched(self):
        db = _synthetic_db(legacy_row=_legacy_unstake(amount=100.0, at=1400.0))
        _patch_atomic_db(self, db)

        result = staking_service.unstake_locked(UID, POSITION_ID)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(db["stake_positions"][POSITION_ID]["status"], "unlocked")

    def test_position_linked_unstake_is_not_legacy_ambiguity(self):
        db = _synthetic_db(
            legacy_row=_legacy_unstake(
                amount=100.0, at=1049.0, position_id=POSITION_ID
            )
        )
        _patch_atomic_db(self, db)

        result = staking_service.unstake_locked(UID, POSITION_ID)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(
            db["ledger"][-1]["meta"]["idempotency_key"],
            f"unstake:{POSITION_ID}",
        )

    def test_repeated_unstake_by_position_id_is_idempotent(self):
        db = _synthetic_db()
        _patch_atomic_db(self, db)

        first = staking_service.unstake_locked(UID, POSITION_ID)
        after_first = copy.deepcopy(db)
        second = staking_service.unstake_locked(UID, POSITION_ID)

        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "already_unlocked")
        self.assertEqual(db, after_first)
        self.assertEqual(db["users"][UID]["wallet"]["credits"], 600.0)
        self.assertEqual(db["users"][UID]["wallet"]["staked"], 200.0)
        self.assertEqual(len(db["ledger"]), 1)


if __name__ == "__main__":
    unittest.main()
