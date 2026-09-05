import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import state_manager
from core.onchain_claim_authority import record_bnb_deposit


class BNBClaimAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "db.json"
        self.db_path.write_text(
            json.dumps({"users": {"100": {"wallet": {"credits": 10}}}}),
            encoding="utf-8",
        )
        self.lock_path = Path(str(self.db_path) + ".lock")
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

    def test_first_claim_is_atomic_and_recorded(self):
        result = record_bnb_deposit("100", 500, 0.5, "0xabc")
        self.assertEqual(result["status"], "applied")
        self.assertEqual(result["balance"], 510)

        db = self.read_db()
        self.assertEqual(db["users"]["100"]["wallet"]["credits"], 510)
        self.assertIn("0xabc", db["claimed_deposits"])
        self.assertEqual(len(db["transactions"]), 1)
        self.assertEqual(len(db["ledger"]), 1)

    def test_sequential_duplicate_does_not_credit_twice(self):
        first = record_bnb_deposit("100", 500, 0.5, "0xabc")
        second = record_bnb_deposit("100", 500, 0.5, "0xabc")

        self.assertEqual(first["status"], "applied")
        self.assertEqual(second["status"], "duplicate")

        db = self.read_db()
        self.assertEqual(db["users"]["100"]["wallet"]["credits"], 510)
        self.assertEqual(len(db["transactions"]), 1)
        self.assertEqual(len(db["ledger"]), 1)

    def test_existing_legacy_transaction_blocks_recredit(self):
        db = self.read_db()
        db["transactions"] = [
            {
                "uid": "100",
                "credits": 500,
                "type": "bnb",
                "amount_bnb": 0.5,
                "tx_hash": "0xlegacy",
            }
        ]
        self.db_path.write_text(json.dumps(db), encoding="utf-8")

        result = record_bnb_deposit("100", 500, 0.5, "0xlegacy")
        self.assertEqual(result["status"], "duplicate")

        db = self.read_db()
        self.assertEqual(db["users"]["100"]["wallet"]["credits"], 10)
        self.assertEqual(len(db["transactions"]), 1)


if __name__ == "__main__":
    unittest.main()
