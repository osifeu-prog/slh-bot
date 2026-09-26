import base64
import hashlib
import struct
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core import ton_wallet_binding


RAW_ADDRESS = "0:" + "11" * 32
DOMAIN = "slh-nft.com"
UID = "12345"


def sign_data_digest(address_raw, domain, timestamp, text):
    workchain, addr_hex = address_raw.split(":", 1)
    domain_bytes = domain.encode("utf-8")
    data_bytes = text.encode("utf-8")
    message = (
        b"\xff\xff"
        + b"ton-connect/sign-data/"
        + struct.pack(">i", int(workchain))
        + bytes.fromhex(addr_hex)
        + struct.pack(">I", len(domain_bytes))
        + domain_bytes
        + struct.pack(">Q", int(timestamp))
        + b"txt"
        + struct.pack(">I", len(data_bytes))
        + data_bytes
    )
    return hashlib.sha256(message).digest()


def proof_digest(address_raw, domain, timestamp, payload):
    workchain, addr_hex = address_raw.split(":", 1)
    message = (
        b"ton-proof-item-v2/"
        + struct.pack(">i", int(workchain))
        + bytes.fromhex(addr_hex)
        + struct.pack("<I", len(domain.encode("utf-8")))
        + domain.encode("utf-8")
        + struct.pack("<Q", int(timestamp))
        + payload.encode("utf-8")
    )
    message_hash = hashlib.sha256(message).digest()
    return hashlib.sha256(b"\xff\xffton-connect" + message_hash).digest()


class TonWalletBindingTests(unittest.TestCase):
    def setUp(self):
        self.db = {}
        self.private_key = Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key().public_bytes_raw().hex()

        def atomic_update(fn):
            return fn(self.db)

        self.atomic_patch = patch.object(
            ton_wallet_binding.state_manager,
            "atomic_update",
            side_effect=atomic_update,
        )
        self.load_patch = patch.object(
            ton_wallet_binding.state_manager,
            "load_db",
            side_effect=lambda: self.db,
        )
        self.state_init_patch = patch.object(
            ton_wallet_binding,
            "_get_state_init_info",
            return_value={"address": RAW_ADDRESS, "public_key": bytes.fromhex(self.public_key)},
        )
        self.atomic_patch.start()
        self.load_patch.start()
        self.state_init_patch.start()
        self.addCleanup(self.atomic_patch.stop)
        self.addCleanup(self.load_patch.stop)
        self.addCleanup(self.state_init_patch.stop)

    def _proof(self, payload, timestamp=None, address=RAW_ADDRESS, public_key=None):
        ts = int(timestamp or datetime.now(timezone.utc).timestamp())
        digest = proof_digest(address, DOMAIN, ts, payload)
        signature = self.private_key.sign(digest)
        return {
            "address": address,
            "network": "-239",
            "public_key": public_key or self.public_key,
            "wallet_state_init": "state-init-fixture",
            "proof": {
                "timestamp": ts,
                "domain": {
                    "lengthBytes": len(DOMAIN.encode("utf-8")),
                    "value": DOMAIN,
                },
                "signature": base64.b64encode(signature).decode("ascii"),
                "payload": payload,
            },
        }

    def test_valid_proof_binds_wallet(self):
        challenge = ton_wallet_binding.issue_ton_challenge(UID, domain=DOMAIN)
        result = ton_wallet_binding.verify_ton_proof(UID, self._proof(challenge["payload"]))
        self.assertEqual(result["uid"], UID)
        self.assertEqual(result["address"], RAW_ADDRESS)
        self.assertEqual(result["network"], "-239")
        self.assertTrue(self.db["ton_wallet_challenges"][UID]["consumed"])

    def test_valid_sign_data_binds_wallet(self):
        challenge = ton_wallet_binding.issue_ton_challenge(UID, domain=DOMAIN)
        ts = int(datetime.now(timezone.utc).timestamp())
        digest = sign_data_digest(
            RAW_ADDRESS,
            DOMAIN,
            ts,
            challenge["sign_data_message"],
        )
        signature = self.private_key.sign(digest)
        result = ton_wallet_binding.verify_ton_sign_data(
            UID,
            {
                "address": RAW_ADDRESS,
                "network": "-239",
                "wallet_state_init": "state-init-fixture",
                "signature": base64.b64encode(signature).decode("ascii"),
                "timestamp": ts,
                "domain": DOMAIN,
                "payload": {
                    "type": "text",
                    "text": challenge["sign_data_message"],
                },
            },
        )
        self.assertEqual(result["uid"], UID)
        self.assertEqual(result["address"], RAW_ADDRESS)
        self.assertEqual(result["verification_method"], "ton_sign_data")
        self.assertTrue(self.db["ton_wallet_challenges"][UID]["consumed"])

    def test_invalid_sign_data_signature_rejected(self):
        challenge = ton_wallet_binding.issue_ton_challenge(UID, domain=DOMAIN)
        ts = int(datetime.now(timezone.utc).timestamp())
        with self.assertRaisesRegex(ValueError, "INVALID_TON_SIGN_DATA"):
            ton_wallet_binding.verify_ton_sign_data(
                UID,
                {
                    "address": RAW_ADDRESS,
                    "network": "-239",
                    "wallet_state_init": "state-init-fixture",
                    "signature": base64.b64encode(b"0" * 64).decode("ascii"),
                    "timestamp": ts,
                    "domain": DOMAIN,
                    "payload": {
                        "type": "text",
                        "text": challenge["sign_data_message"],
                    },
                },
            )

    def test_invalid_signature_rejected(self):
        challenge = ton_wallet_binding.issue_ton_challenge(UID, domain=DOMAIN)
        bad = self._proof(challenge["payload"], public_key=self.public_key)
        bad["proof"]["signature"] = base64.b64encode(b"0" * 64).decode("ascii")
        with self.assertRaisesRegex(ValueError, "INVALID_TON_PROOF"):
            ton_wallet_binding.verify_ton_proof(UID, bad)

    def test_expired_challenge_rejected(self):
        challenge = ton_wallet_binding.issue_ton_challenge(UID, domain=DOMAIN, ttl_seconds=1)
        self.db["ton_wallet_challenges"][UID]["expires_at"] = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
        proof = self._proof(challenge["payload"])
        with self.assertRaisesRegex(ValueError, "TON_CHALLENGE_EXPIRED"):
            ton_wallet_binding.verify_ton_proof(UID, proof)

    def test_reused_challenge_rejected(self):
        challenge = ton_wallet_binding.issue_ton_challenge(UID, domain=DOMAIN)
        proof = self._proof(challenge["payload"])
        ton_wallet_binding.verify_ton_proof(UID, proof)
        with self.assertRaisesRegex(ValueError, "TON_CHALLENGE_CONSUMED"):
            ton_wallet_binding.verify_ton_proof(UID, proof)

    def test_wallet_cannot_bind_to_second_user(self):
        challenge = ton_wallet_binding.issue_ton_challenge(UID, domain=DOMAIN)
        ton_wallet_binding.verify_ton_proof(UID, self._proof(challenge["payload"]))

        second_uid = "67890"
        challenge2 = ton_wallet_binding.issue_ton_challenge(second_uid, domain=DOMAIN)
        with self.assertRaisesRegex(ValueError, "TON_WALLET_ALREADY_BOUND"):
            ton_wallet_binding.verify_ton_proof(second_uid, self._proof(challenge2["payload"]))


if __name__ == "__main__":
    unittest.main()
