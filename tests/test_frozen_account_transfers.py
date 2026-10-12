import copy
import unittest
from unittest.mock import patch

import core.slh_distribution as distribution


class FrozenAccountCanonicalLedgerTests(unittest.TestCase):
    def setUp(self):
        self.db = {
            "users": {
                "frozen": {
                    "frozen": True,
                    "frozen_reason": "unbacked_test_distribution_20260922",
                    "wallet": {
                        "token_balance": 50000.0,
                        "live_token_balance": 50000.0,
                        "exchange_reserved_slh": 0.0,
                        "exchange_reserved_credits": 0.0,
                        "credits": 0.0,
                    },
                },
                "sender": {
                    "wallet": {
                        "token_balance": 10.0,
                        "live_token_balance": 10.0,
                        "exchange_reserved_slh": 0.0,
                        "exchange_reserved_credits": 0.0,
                        "credits": 0.0,
                    },
                },
                "buyer": {
                    "wallet": {
                        "token_balance": 0.0,
                        "live_token_balance": 0.0,
                        "exchange_reserved_slh": 0.0,
                        "exchange_reserved_credits": 0.0,
                        "credits": 10.0,
                    },
                },
            },
        }

    def test_frozen_sender_cannot_p2p_transfer_slh(self):
        before = copy.deepcopy(self.db)
        with patch.object(
            distribution.state_manager,
            "atomic_update",
            side_effect=lambda mutate: mutate(self.db),
        ):
            with self.assertRaisesRegex(ValueError, "ACCOUNT_FROZEN"):
                distribution.transfer(
                    sender_uid="frozen",
                    recipient_uid="sender",
                    amount=1,
                    event_id="test-frozen-p2p-1",
                    reason="p2p:slh",
                )
        self.assertEqual(self.db, before)

    def test_frozen_sender_cannot_reserve_slh_for_exchange(self):
        before = copy.deepcopy(self.db)
        with self.assertRaisesRegex(ValueError, "ACCOUNT_FROZEN"):
            distribution.reserve_in_db(
                self.db,
                uid="frozen",
                amount=1,
                event_id="test-frozen-reserve-1",
                order_id="O-TEST",
            )
        self.assertEqual(self.db, before)

    def test_settlement_is_blocked_if_either_participant_is_frozen(self):
        for frozen_uid in ("frozen", "buyer"):
            with self.subTest(frozen_uid=frozen_uid):
                db = copy.deepcopy(self.db)
                if frozen_uid == "buyer":
                    db["users"]["frozen"].pop("frozen", None)
                    db["users"]["buyer"]["frozen"] = True
                before = copy.deepcopy(db)
                with self.assertRaisesRegex(ValueError, "ACCOUNT_FROZEN"):
                    distribution.settle_reserve_in_db(
                        db,
                        seller_uid="frozen",
                        buyer_uid="buyer",
                        amount=1,
                        event_id="test-frozen-settlement-" + frozen_uid,
                        order_id="O-TEST",
                        trade_id="T-TEST",
                    )
                self.assertEqual(db, before)


if __name__ == "__main__":
    unittest.main()
