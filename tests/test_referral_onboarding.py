"""Regression test for referral persistence idempotency."""

import importlib
import json
import tempfile
from pathlib import Path

import state_manager


def test_referral_relationship_persists_once_and_does_not_repeat_reward():
    tmp = tempfile.TemporaryDirectory()
    try:
        db_path = Path(tmp.name) / "db.json"
        db_path.write_text(
            json.dumps(
                {
                    "users": {
                        "100": {"referral": {}},
                        "200": {"referral": {}},
                    },
                    "pending_referrals": {"200": "100"},
                }
            ),
            encoding="utf-8",
        )
        state_manager.DB_FILE = str(db_path)
        state_manager._LOCK_PATH = str(db_path) + ".lock"

        import handlers.join_handler as join_handler
        join_handler = importlib.reload(join_handler)

        assert join_handler._persist_referral("200", "100") is True
        db = state_manager.load_db()
        assert db["users"]["200"]["referral"]["referred_by"] == "100"
        assert db["users"]["100"]["referral"]["count"] == 1

        # A repeated finalization must not report a new persistence event.
        assert join_handler._persist_referral("200", "100") is False
        db = state_manager.load_db()
        assert db["users"]["100"]["referral"]["count"] == 1
    finally:
        tmp.cleanup()
