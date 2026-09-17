import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.legacy_wallet_migration import record_legacy_claim


class LegacyWalletMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "db.json"
        self.db_path.write_text(
            json.dumps(
                {
                    "users": {
                        "100": {"wallet": {"credits": 10}},
                        "200": {"wallet": {"credits": 0}},
                    }
                }
            ),
            encoding="utf-8",
        )
        self.patches = [
            patch.object(
                __import__("state_manager"),
                "load_db",
                side_effect=lambda: json.loads(self.db_path.read_text(encoding="utf-8")),
            ),
            patch.object(
                __import__("state_manager"),
                "atomic_update",
                side_effect=self.atomic_update,
            ),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(self._cleanup_patches)

    def _cleanup_patches(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def atomic_update(self, fn):
        db = json.loads(self.db_path.read_text(encoding="utf-8"))
        result = fn(db)
        self.db_path.write_text(json.dumps(db), encoding="utf-8")
        return result

    def test_first_claim_binds_legacy_wallet_once(self):
        wallet = "0x0000000000000000000000000000000000000ABC"
        result = record_legacy_claim("100", wallet, 123.5)

        self.assertEqual(result["status"], "claimed")
        self.assertEqual(result["uid"], "100")
        self.assertEqual(result["wallet"], wallet)

        db = json.loads(self.db_path.read_text(encoding="utf-8"))
        self.assertEqual(
            db["legacy_wallet_migrations"][wallet.lower()]["uid"],
            "100",
        )
        self.assertEqual(
            db["users"]["100"]["wallet"]["legacy_bnb_wallet"],
            wallet,
        )

    def test_duplicate_claim_is_idempotent(self):
        wallet = "0x0000000000000000000000000000000000000ABC"
        record_legacy_claim("100", wallet, 123.5)
        result = record_legacy_claim("100", wallet, 123.5)
        self.assertEqual(result["status"], "duplicate")

    def test_wallet_cannot_be_claimed_by_second_user(self):
        wallet = "0x0000000000000000000000000000000000000ABC"
        record_legacy_claim("100", wallet, 123.5)
        with self.assertRaisesRegex(ValueError, "WALLET_ALREADY_MIGRATED"):
            record_legacy_claim("200", wallet, 123.5)


if __name__ == "__main__":
    unittest.main()
