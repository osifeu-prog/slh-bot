import unittest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta

from eth_account import Account
from eth_account.messages import encode_defunct

from core import wallet_binding


class WalletBindingTests(unittest.TestCase):
    def setUp(self):
        self.db = {}
        self.account = Account.create()
        self.uid = "test-user"
        self.address = self.account.address

        def atomic_update(fn):
            return fn(self.db)

        self.atomic_patch = patch.object(wallet_binding.state_manager, "atomic_update", side_effect=atomic_update)
        self.load_patch = patch.object(wallet_binding.state_manager, "load_db", side_effect=lambda: self.db)
        self.atomic_patch.start()
        self.load_patch.start()
        self.addCleanup(self.atomic_patch.stop)
        self.addCleanup(self.load_patch.stop)

    def test_valid_signature_binds_wallet_and_consumes_challenge(self):
        challenge = wallet_binding.issue_challenge(self.uid, self.address)
        signature = self.account.sign_message(encode_defunct(text=challenge["message"])).signature.hex()

        binding = wallet_binding.verify_signature(self.uid, self.address, signature)

        self.assertEqual(binding["uid"], self.uid)
        self.assertEqual(binding["address"], self.address)
        self.assertTrue(self.db["wallet_challenges"]["bsc:test-user"]["consumed"])

    def test_replay_is_rejected(self):
        challenge = wallet_binding.issue_challenge(self.uid, self.address)
        signature = self.account.sign_message(encode_defunct(text=challenge["message"])).signature.hex()
        wallet_binding.verify_signature(self.uid, self.address, signature)

        with self.assertRaisesRegex(ValueError, "CHALLENGE_NOT_FOUND"):
            wallet_binding.verify_signature(self.uid, self.address, signature)

    def test_wrong_wallet_signature_is_rejected(self):
        challenge = wallet_binding.issue_challenge(self.uid, self.address)
        other = Account.create()
        signature = other.sign_message(encode_defunct(text=challenge["message"])).signature.hex()

        with self.assertRaisesRegex(ValueError, "WALLET_OWNERSHIP_NOT_PROVEN"):
            wallet_binding.verify_signature(self.uid, self.address, signature)

    def test_expired_challenge_is_rejected(self):
        challenge = wallet_binding.issue_challenge(self.uid, self.address)
        self.db["wallet_challenges"]["bsc:test-user"]["expires_at"] = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
        signature = self.account.sign_message(encode_defunct(text=challenge["message"])).signature.hex()

        with self.assertRaisesRegex(ValueError, "CHALLENGE_EXPIRED"):
            wallet_binding.verify_signature(self.uid, self.address, signature)

    def test_same_wallet_cannot_bind_to_second_user(self):
        challenge = wallet_binding.issue_challenge(self.uid, self.address)
        signature = self.account.sign_message(encode_defunct(text=challenge["message"])).signature.hex()
        wallet_binding.verify_signature(self.uid, self.address, signature)

        second_uid = "second-user"
        challenge2 = wallet_binding.issue_challenge(second_uid, self.address)
        signature2 = self.account.sign_message(encode_defunct(text=challenge2["message"])).signature.hex()

        with self.assertRaisesRegex(ValueError, "WALLET_ALREADY_BOUND"):
            wallet_binding.verify_signature(second_uid, self.address, signature2)


if __name__ == "__main__":
    unittest.main()
