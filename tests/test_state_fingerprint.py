import hashlib
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import state_manager
from core.state_fingerprint import build_local_state_fingerprint


class LocalStateFingerprintTests(unittest.TestCase):
    def test_fingerprint_is_aggregate_only_and_does_not_mutate_file(self):
        sensitive_uid = "PRIVATE-USER-123"
        raw = json.dumps({
            "users": {sensitive_uid: {"wallet": {"credits": 987654.321, "staked": 19}}},
            "ledger": [{"uid": sensitive_uid, "amount": -987654.321, "reason": "PRIVATE-LEDGER-CONTENT"}],
            "slh_token_ledger": [],
            "exchange_orders": {"PRIVATE-ORDER-456": {"status": "open"}},
        }, separators=(",", ":")).encode("utf-8")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "db.json"
            path.write_bytes(raw)
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            with patch("state_manager.DB_FILE", str(path)), patch(
                "state_manager._db_lock", return_value=nullcontext()
            ):
                result = build_local_state_fingerprint()

            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["read_only"])
            self.assertEqual(result["snapshot"]["sha256"], before)
            self.assertEqual(result["snapshot"]["size_bytes"], len(raw))
            self.assertEqual(result["snapshot"]["collections"]["users"], {"type": "object", "count": 1})
            self.assertEqual(result["snapshot"]["collections"]["ledger"], {"type": "array", "count": 1})
            self.assertEqual(result["snapshot"]["collections"]["slh_token_ledger"], {"type": "array", "count": 0})
            encoded = json.dumps(result, ensure_ascii=False)
            for private_value in (sensitive_uid, "987654.321", "PRIVATE-LEDGER-CONTENT", "PRIVATE-ORDER-456"):
                self.assertNotIn(private_value, encoded)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def test_malformed_json_fails_closed_without_rewriting_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "db.json"
            path.write_text("{ malformed", encoding="utf-8")
            before = path.read_bytes()
            with patch("state_manager.DB_FILE", str(path)), patch(
                "state_manager._db_lock", return_value=nullcontext()
            ):
                with self.assertRaisesRegex(ValueError, "STATE_FILE_INVALID_JSON"):
                    build_local_state_fingerprint()
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
