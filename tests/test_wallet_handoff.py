import unittest
from unittest.mock import patch

from core import wallet_handoff


class WalletHandoffTests(unittest.TestCase):
    def setUp(self):
        self.db = {}
        self.uid = "8789977826"

        def atomic_update(fn):
            return fn(self.db)

        self.atomic_patch = patch.object(
            wallet_handoff.state_manager,
            "atomic_update",
            side_effect=atomic_update,
        )
        self.load_patch = patch.object(
            wallet_handoff.state_manager,
            "load_db",
            side_effect=lambda: self.db,
        )
        self.atomic_patch.start()
        self.load_patch.start()
        self.addCleanup(self.atomic_patch.stop)
        self.addCleanup(self.load_patch.stop)

    def test_handoff_can_be_consumed_only_once(self):
        handoff = wallet_handoff.create_handoff(self.uid)
        self.assertEqual(wallet_handoff.consume_handoff(handoff["token"]), self.uid)

        with self.assertRaisesRegex(ValueError, "WALLET_HANDOFF_ALREADY_CONSUMED"):
            wallet_handoff.consume_handoff(handoff["token"])

    def test_session_remains_valid_after_consumption(self):
        handoff = wallet_handoff.create_handoff(self.uid)
        wallet_handoff.consume_handoff(handoff["token"])
        self.assertEqual(wallet_handoff.validate_session(handoff["token"]), self.uid)

    def test_unknown_token_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "WALLET_HANDOFF_NOT_FOUND"):
            wallet_handoff.consume_handoff("a" * 32)


if __name__ == "__main__":
    unittest.main()
