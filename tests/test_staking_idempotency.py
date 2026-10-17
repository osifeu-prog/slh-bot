import copy
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


    def test_frozen_user_cannot_create_new_staking_position(self):
        db = self.read_db()
        db["users"]["u1"]["frozen"] = True
        self.db_path.write_text(json.dumps(db), encoding="utf-8")
        before = self.read_db()

        with self.assertRaisesRegex(ValueError, "ACCOUNT_FROZEN"):
            staking_service.stake_locked(
                "u1", 10, lock_days=30, request_id="frozen-new-stake",
            )

        self.assertEqual(self.read_db(), before)
        self.assertNotIn("stake_positions", before)
        self.assertNotIn("ledger", before)

    def test_frozen_user_can_retry_exact_existing_stake_without_second_debit(self):
        first = staking_service.stake_locked(
            "u1", 10, lock_days=30, request_id="retry-before-freeze",
        )
        db = self.read_db()
        db["users"]["u1"]["frozen"] = True
        self.db_path.write_text(json.dumps(db), encoding="utf-8")
        before_retry = self.read_db()

        replay = staking_service.stake_locked(
            "u1", 10, lock_days=30, request_id="retry-before-freeze",
        )

        self.assertEqual(replay["status"], "duplicate")
        self.assertEqual(replay["position"]["id"], first["position"]["id"])
        self.assertEqual(self.read_db(), before_retry)
        final = self.read_db()
        self.assertEqual(final["users"]["u1"]["wallet"]["credits"], 90.0)
        self.assertEqual(final["users"]["u1"]["wallet"]["staked"], 10.0)
        self.assertEqual(len(final["stake_positions"]), 1)
        self.assertEqual(len([
            row for row in final["ledger"]
            if row.get("reason") == "staking:stake_locked"
        ]), 1)



if __name__ == "__main__":
    unittest.main()
