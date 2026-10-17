import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import state_manager
from core import staking_service


class StakingIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "db.json"
        self.lock_path = Path(str(self.db_path) + ".lock")
        self.db_path.write_text(
            json.dumps({
                "users": {
                    "u1": {"wallet": {"credits": 100.0, "staked": 0.0}}
                }
            }),
            encoding="utf-8",
        )
        self.patches = [
            patch.object(state_manager, "DB_FILE", str(self.db_path)),
            patch.object(state_manager, "_LOCK_PATH", str(self.lock_path)),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def read_db(self):
        return json.loads(self.db_path.read_text(encoding="utf-8"))

    def test_same_request_id_stakes_once(self):
        first = staking_service.stake_locked(
            "u1", 10, lock_days=30, request_id="req-1",
            meta={"source": "test"},
        )
        second = staking_service.stake_locked(
            "u1", 10, lock_days=30, request_id="req-1",
            meta={"source": "test"},
        )

        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(first["position"]["id"], second["position"]["id"])

        db = self.read_db()
        wallet = db["users"]["u1"]["wallet"]
        self.assertEqual(wallet["credits"], 90.0)
        self.assertEqual(wallet["staked"], 10.0)
        self.assertEqual(len(db["stake_positions"]), 1)
        self.assertEqual(len(db["staking_requests"]), 1)
        self.assertEqual(len([
            x for x in db["ledger"]
            if x.get("reason") == "staking:stake_locked"
        ]), 1)

    def test_same_unstake_request_does_not_double_release(self):
        created = staking_service.stake_locked(
            "u1", 10, lock_days=1, request_id="stake-1",
        )
        pid = created["position"]["id"]

        db = self.read_db()
        db["stake_positions"][pid]["unlocks_at"] = 0
        self.db_path.write_text(json.dumps(db), encoding="utf-8")

        first = staking_service.unstake_locked(
            "u1", pid, request_id="unstake-1",
        )
        second = staking_service.unstake_locked(
            "u1", pid, request_id="unstake-1",
        )

        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "duplicate")
        db = self.read_db()
        wallet = db["users"]["u1"]["wallet"]
        self.assertEqual(wallet["credits"], 100.0)
        self.assertEqual(wallet["staked"], 0.0)


    def test_same_stake_request_id_with_different_amount_fails_without_mutation(self):
        staking_service.stake_locked("u1", 10, lock_days=30, request_id="stable-stake")
        before = self.read_db()

        with self.assertRaisesRegex(ValueError, "STAKING_REQUEST_IDENTITY_CONFLICT"):
            staking_service.stake_locked("u1", 11, lock_days=30, request_id="stable-stake")

        self.assertEqual(self.read_db(), before)

    def test_same_stake_request_id_with_different_lock_days_fails_without_mutation(self):
        staking_service.stake_locked("u1", 10, lock_days=30, request_id="stable-stake-lock")
        before = self.read_db()

        with self.assertRaisesRegex(ValueError, "STAKING_REQUEST_IDENTITY_CONFLICT"):
            staking_service.stake_locked("u1", 10, lock_days=60, request_id="stable-stake-lock")

        self.assertEqual(self.read_db(), before)

    def test_boolean_stake_amount_is_rejected_before_db_mutation(self):
        before = self.read_db()

        with self.assertRaisesRegex(ValueError, "INVALID_STAKING_REQUEST"):
            staking_service.stake_locked("u1", True, lock_days=30, request_id="bool-stake")

        self.assertEqual(self.read_db(), before)

    def test_fractional_lock_days_are_rejected_before_db_mutation(self):
        before = self.read_db()

        with self.assertRaisesRegex(ValueError, "INVALID_STAKING_REQUEST"):
            staking_service.stake_locked("u1", 10, lock_days=30.5, request_id="fractional-lock")

        self.assertEqual(self.read_db(), before)

    def test_missing_users_store_is_not_created_by_rejected_stake(self):
        self.db_path.write_text(json.dumps({"ledger": []}), encoding="utf-8")
        before = self.read_db()

        with self.assertRaisesRegex(ValueError, "INVALID_USERS_STATE"):
            staking_service.stake_locked("u1", 10, lock_days=30, request_id="missing-users")

        self.assertEqual(self.read_db(), before)

    def test_nan_stake_amount_is_rejected_before_db_mutation(self):
        before = self.read_db()

        with self.assertRaisesRegex(ValueError, "finite positive"):
            staking_service.stake_locked("u1", float("nan"), lock_days=30, request_id="nan-stake")

        self.assertEqual(self.read_db(), before)

    def test_nan_unstake_unlock_time_fails_closed_without_mutation(self):
        created = staking_service.stake_locked(
            "u1", 10, lock_days=1, request_id="stake-nan-unlock",
        )
        db = self.read_db()
        position_id = created["position"]["id"]
        db["stake_positions"][position_id]["unlocks_at"] = float("nan")
        self.db_path.write_text(json.dumps(db), encoding="utf-8")
        before = self.read_db()

        with self.assertRaisesRegex(ValueError, "INVALID_STAKE_POSITION"):
            staking_service.unstake_locked("u1", position_id, request_id="nan-unlock")

        self.assertEqual(self.read_db(), before)

    def test_non_list_ledger_blocks_unstake_before_wallet_mutation(self):
        created = staking_service.stake_locked(
            "u1", 10, lock_days=1, request_id="stake-bad-ledger",
        )
        db = self.read_db()
        position_id = created["position"]["id"]
        db["stake_positions"][position_id]["unlocks_at"] = 0
        db["ledger"] = {"corrupt": True}
        self.db_path.write_text(json.dumps(db), encoding="utf-8")
        before = self.read_db()

        with self.assertRaisesRegex(ValueError, "INVALID_LEDGER_STATE"):
            staking_service.unstake_locked("u1", position_id, request_id="bad-ledger-unstake")

        self.assertEqual(self.read_db(), before)

    def test_unstake_request_id_cannot_be_reused_for_a_different_position(self):
        first_position = staking_service.stake_locked("u1", 10, lock_days=1, request_id="stake-a")
        second_position = staking_service.stake_locked("u1", 10, lock_days=1, request_id="stake-b")
        db = self.read_db()
        db["stake_positions"][first_position["position"]["id"]]["unlocks_at"] = 0
        db["stake_positions"][second_position["position"]["id"]]["unlocks_at"] = 0
        self.db_path.write_text(json.dumps(db), encoding="utf-8")

        staking_service.unstake_locked(
            "u1", first_position["position"]["id"], request_id="shared-unstake",
        )
        before = self.read_db()

        with self.assertRaisesRegex(ValueError, "STAKING_UNSTAKE_IDENTITY_CONFLICT"):
            staking_service.unstake_locked(
                "u1", second_position["position"]["id"], request_id="shared-unstake",
            )

        self.assertEqual(self.read_db(), before)

if __name__ == "__main__":
    unittest.main()
