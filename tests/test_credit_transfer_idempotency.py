import copy
import unittest
from unittest.mock import patch

from core import economy_service


class CreditTransferIdempotencyTests(unittest.TestCase):
    def _db(self):
        return {
            "users": {
                "sender": {"wallet": {"credits": 100.0}},
                "recipient": {"wallet": {"credits": 20.0}},
                "other": {"wallet": {"credits": 7.0}},
            },
            "ledger": [],
            "processed_transfers": {},
        }

    def _run(self, db, sender, recipient, amount, key="transfer-key"):
        with patch.object(
            economy_service.state_manager,
            "atomic_update",
            side_effect=lambda mutate: mutate(db),
        ):
            return economy_service.transfer_credits(
                sender_uid=sender,
                recipient_uid=recipient,
                amount=amount,
                idempotency_key=key,
                meta={"source": "unit_test"},
            )

    def test_exact_retry_returns_original_transfer_without_mutation(self):
        db = self._db()
        first = self._run(db, "sender", "recipient", 10)
        before_retry = copy.deepcopy(db)

        # A retry must not be rejected merely because the current balance
        # would no longer cover another debit.
        db["users"]["sender"]["wallet"]["credits"] = 2.0
        before_retry = copy.deepcopy(db)
        replay = self._run(db, "sender", "recipient", 10)

        self.assertEqual(replay["status"], "duplicate")
        self.assertEqual(replay["transfer_id"], first["transfer_id"])
        self.assertEqual(replay["amount"], 10.0)
        self.assertEqual(replay["recipient_uid"], "recipient")
        self.assertEqual(replay["sender_balance"], 2.0)
        self.assertEqual(db, before_retry)
        self.assertEqual(len(db["ledger"]), 2)
        self.assertIsInstance(db["processed_transfers"]["transfer-key"], dict)

    def test_same_key_with_different_recipient_is_conflict(self):
        db = self._db()
        self._run(db, "sender", "recipient", 10)
        before = copy.deepcopy(db)

        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_CONFLICT"):
            self._run(db, "sender", "other", 10)

        self.assertEqual(db, before)

    def test_same_key_with_different_amount_is_conflict(self):
        db = self._db()
        self._run(db, "sender", "recipient", 10)
        before = copy.deepcopy(db)

        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_CONFLICT"):
            self._run(db, "sender", "recipient", 12)

        self.assertEqual(db, before)

    def test_same_key_with_different_sender_is_conflict(self):
        db = self._db()
        self._run(db, "sender", "recipient", 10)
        before = copy.deepcopy(db)

        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_CONFLICT"):
            self._run(db, "other", "recipient", 10)

        self.assertEqual(db, before)

    def test_legacy_key_to_transfer_id_replay_is_reconstructed_from_ledger(self):
        db = self._db()
        transfer_id = "TRANSFER-LEGACY-1"
        db["users"]["sender"]["wallet"]["credits"] = 90.0
        db["users"]["recipient"]["wallet"]["credits"] = 30.0
        db["processed_transfers"]["legacy-key"] = transfer_id
        db["ledger"] = [
            {
                "uid": "sender",
                "before": 100.0,
                "amount": -10.0,
                "after": 90.0,
                "reason": "p2p:transfer_sent",
                "meta": {"transfer_id": transfer_id, "recipient_uid": "recipient"},
            },
            {
                "uid": "recipient",
                "before": 20.0,
                "amount": 10.0,
                "after": 30.0,
                "reason": "p2p:transfer_received",
                "meta": {"transfer_id": transfer_id, "sender_uid": "sender"},
            },
        ]
        before = copy.deepcopy(db)

        replay = self._run(db, "sender", "recipient", 10, key="legacy-key")

        self.assertEqual(replay["status"], "duplicate")
        self.assertEqual(replay["transfer_id"], transfer_id)
        self.assertEqual(replay["recipient_uid"], "recipient")
        self.assertEqual(db, before)

    def test_legacy_key_without_matching_ledger_identity_fails_closed(self):
        db = self._db()
        db["processed_transfers"]["orphan-key"] = "TRANSFER-MISSING"
        before = copy.deepcopy(db)

        with self.assertRaisesRegex(ValueError, "LEGACY_TRANSFER_IDENTITY_UNKNOWN"):
            self._run(db, "sender", "recipient", 10, key="orphan-key")

        self.assertEqual(db, before)


if __name__ == "__main__":
    unittest.main()
