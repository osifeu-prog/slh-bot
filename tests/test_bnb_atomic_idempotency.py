import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from core import economy_service


class AtomicTransactionIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.db = {
            "users": {
                "u1": {"wallet": {"credits": 0}},
                "u2": {"wallet": {"credits": 0}},
            },
            "ledger": [],
        }
        self.lock = threading.Lock()

        def atomic_update(mutate):
            with self.lock:
                return mutate(self.db)

        self.atomic_patch = patch.object(
            economy_service.state_manager, "atomic_update", side_effect=atomic_update
        )
        self.atomic_patch.start()
        self.addCleanup(self.atomic_patch.stop)

    def _record(self, uid="u1", amount=100, **meta_overrides):
        meta = {
            "idempotency_key": "bnb:deposit:0xabc",
            "tx_hash": "0xabc",
            "bnb_amount_wei": 100000000000000000,
            "from": "0xSender",
            "to": "0xTreasury",
        }
        meta.update(meta_overrides)
        return economy_service.record_transaction(
            uid, amount, reason="bnb:deposit", meta=meta, return_details=True
        )

    def test_concurrent_replay_applies_credit_once_and_reports_duplicate(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self._record(), range(8)))

        statuses = [row["status"] for row in results]
        self.assertEqual(statuses.count("APPLIED"), 1)
        self.assertEqual(statuses.count("DUPLICATE"), 7)
        self.assertEqual(self.db["users"]["u1"]["wallet"]["credits"], 100)
        self.assertEqual(len(self.db["ledger"]), 1)

    def test_same_key_with_different_user_is_conflict(self):
        applied = self._record(uid="u1")
        conflict = self._record(uid="u2")

        self.assertEqual(applied["status"], "APPLIED")
        self.assertEqual(conflict["status"], "CONFLICT")
        self.assertEqual(self.db["users"]["u1"]["wallet"]["credits"], 100)
        self.assertEqual(self.db["users"]["u2"]["wallet"]["credits"], 0)
        self.assertEqual(len(self.db["ledger"]), 1)

    def test_same_key_with_different_amount_is_conflict(self):
        self._record(amount=100)
        conflict = self._record(amount=101)

        self.assertEqual(conflict["status"], "CONFLICT")
        self.assertEqual(self.db["users"]["u1"]["wallet"]["credits"], 100)
        self.assertEqual(len(self.db["ledger"]), 1)


if __name__ == "__main__":
    unittest.main()
