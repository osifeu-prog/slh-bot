import copy
import unittest
from unittest.mock import patch

from core import economy_service


class FrozenCreditP2PTests(unittest.TestCase):
    def _db(self):
        return {
            "users": {
                "frozen-sender": {
                    "frozen": True,
                    "frozen_reason": "policy-test",
                    "wallet": {"credits": 100.0},
                },
                "recipient": {
                    "wallet": {"credits": 5.0},
                },
            },
            "ledger": [],
            "processed_transfers": {},
        }

    def test_frozen_sender_cannot_transfer_credits_and_state_is_unchanged(self):
        db = self._db()
        before = copy.deepcopy(db)
        with patch.object(
            economy_service.state_manager,
            "atomic_update",
            side_effect=lambda mutate: mutate(db),
        ):
            with self.assertRaisesRegex(ValueError, "ACCOUNT_FROZEN"):
                economy_service.transfer_credits(
                    sender_uid="frozen-sender",
                    recipient_uid="recipient",
                    amount=10,
                    idempotency_key="test-frozen-credit-transfer",
                    meta={"source": "unit_test"},
                )

        self.assertEqual(db, before)


if __name__ == "__main__":
    unittest.main()
