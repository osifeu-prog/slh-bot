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


if __name__ == "__main__":
    unittest.main()
