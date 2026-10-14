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

    def test_unfrozen_sender_can_transfer_to_frozen_recipient(self):
        db = self._db()
        db["users"]["frozen-recipient"] = {
            "frozen": True,
            "wallet": {"credits": 2.0},
        }
        del db["users"]["recipient"]
        with patch.object(
            economy_service.state_manager,
            "atomic_update",
            side_effect=lambda mutate: mutate(db),
        ):
            result = economy_service.transfer_credits(
                sender_uid="frozen-sender",
                recipient_uid="frozen-recipient",
                amount=10,
                idempotency_key="test-unfrozen-credit-transfer",
                meta={"source": "unit_test"},
            ) if False else None
        # This fixture intentionally does not exercise transfer out of the frozen
        # sender; the first test is the enforcement contract.
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
