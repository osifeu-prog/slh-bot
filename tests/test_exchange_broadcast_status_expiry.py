import copy
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from handlers import broadcast_handler


OWNER_UID = "8789977826"
NOW = datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc)
GREEN_CHECK = {
    "execution_ready": True,
    "public_gate": "OPEN",
    "verdict": "OPEN",
    "public_ready": True,
    "order_book_integrity": True,
    "trade_integrity": True,
    "money_invariants": True,
    "detail": "public state clean",
}


class ExchangeBroadcastStatusExpiryTests(unittest.TestCase):
    def _reply(self, db):
        with (
            patch.object(broadcast_handler.state_manager, "load_db", return_value=db),
            patch.object(broadcast_handler, "_fresh_exchange_check", return_value=GREEN_CHECK),
        ):
            return broadcast_handler._broadcast_status_reply(
                OWNER_UID, now=NOW
            )

    def test_expired_pending_preview_is_reported_as_expired_without_mutation(self):
        db = {
            "exchange_broadcast_pending": {
                OWNER_UID: {
                    "draft_id": "old-draft",
                    "status": "PENDING_CONFIRMATION",
                    "created_at": "2026-10-10T08:19:52+00:00",
                    "expires_at": "2026-10-10T08:24:52+00:00",
                    "target_count": 32,
                }
            },
            "exchange_broadcast_audit": [],
        }
        before = copy.deepcopy(db)

        reply = self._reply(db)

        self.assertIn("EXPIRED", reply)
        self.assertNotIn("Exchange draft: PENDING_CONFIRMATION", reply)
        self.assertEqual(db, before, "status inspection must remain read-only")

    def test_unexpired_pending_preview_remains_pending(self):
        db = {
            "exchange_broadcast_pending": {
                OWNER_UID: {
                    "draft_id": "fresh-draft",
                    "status": "PENDING_CONFIRMATION",
                    "created_at": "2026-10-10T14:59:00+00:00",
                    "expires_at": "2026-10-10T15:04:00+00:00",
                    "target_count": 32,
                }
            },
            "exchange_broadcast_audit": [],
        }

        reply = self._reply(db)

        self.assertIn("PENDING_CONFIRMATION", reply)
        self.assertNotIn("EXPIRED", reply)

    def test_invalid_expiry_is_failed_closed_in_status(self):
        db = {
            "exchange_broadcast_pending": {
                OWNER_UID: {
                    "draft_id": "bad-expiry",
                    "status": "PENDING_CONFIRMATION",
                    "expires_at": "not-a-time",
                    "target_count": 32,
                }
            },
            "exchange_broadcast_audit": [],
        }

        reply = self._reply(db)

        self.assertIn("EXPIRED", reply)
        self.assertNotIn("Exchange draft: PENDING_CONFIRMATION", reply)


if __name__ == "__main__":
    unittest.main()
