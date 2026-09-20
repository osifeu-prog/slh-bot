"""Regression tests for referral persistence and reward idempotency."""

import importlib
import json
import tempfile
from pathlib import Path

import state_manager


def _seed_db(path):
    path.write_text(
        json.dumps(
            {
                "users": {
                    "100": {"referral": {}, "gamification": {"points": 0, "level": 1, "points_ledger": []}},
                    "200": {"referral": {}, "gamification": {"points": 0, "level": 1, "points_ledger": []}},
                },
                "pending_referrals": {"200": "100"},
            }
        ),
        encoding="utf-8",
    )


def test_referral_relationship_persists_once_and_does_not_repeat_reward():
    tmp = tempfile.TemporaryDirectory()
    try:
        db_path = Path(tmp.name) / "db.json"
        _seed_db(db_path)
        state_manager.DB_FILE = str(db_path)
        state_manager._LOCK_PATH = str(db_path) + ".lock"

        import handlers.join_handler as join_handler
        join_handler = importlib.reload(join_handler)

        assert join_handler._persist_referral("200", "100") is True
        db = state_manager.load_db()
        assert db["users"]["200"]["referral"]["referred_by"] == "100"
        assert db["users"]["100"]["referral"]["count"] == 1

        assert join_handler._persist_referral("200", "100") is False
        db = state_manager.load_db()
        assert db["users"]["100"]["referral"]["count"] == 1
    finally:
        tmp.cleanup()


def test_referral_full_reward_path_is_idempotent():
    """Persist a referral, grant its reward, then prove retry cannot double-pay."""
    tmp = tempfile.TemporaryDirectory()
    try:
        db_path = Path(tmp.name) / "db.json"
        ledger_path = Path(tmp.name) / "rewards_ledger.json"
        _seed_db(db_path)
        state_manager.DB_FILE = str(db_path)
        state_manager._LOCK_PATH = str(db_path) + ".lock"

        import handlers.join_handler as join_handler
        import core.reward_engine as reward_engine
        join_handler = importlib.reload(join_handler)
        reward_engine = importlib.reload(reward_engine)
        reward_engine.LEDGER = ledger_path

        ref_uid = join_handler._get_pending_referral("200")
        assert ref_uid == "100"
        assert join_handler._persist_referral("200", ref_uid) is True

        first = reward_engine.grant(
            "100",
            "referral",
            points=10,
            idempotency_key="ref:200",
        )
        assert first["points"] == 10

        db = state_manager.load_db()
        assert db["users"]["100"]["gamification"]["points"] == 10
        point_entries = [
            x for x in db["users"]["100"]["points_ledger"]
            if x.get("meta", {}).get("idempotency_key") == "ref:200"
        ]
        assert len(point_entries) == 1

        # The same join finalization must not create a second relationship/reward.
        assert join_handler._persist_referral("200", "100") is False
        retry = reward_engine.grant(
            "100",
            "referral",
            points=10,
            idempotency_key="ref:200",
        )
        assert retry["points"] == 10

        db = state_manager.load_db()
        assert db["users"]["100"]["gamification"]["points"] == 10
        point_entries = [
            x for x in db["users"]["100"]["gamification"]["points_ledger"]
            if x.get("meta", {}).get("idempotency_key") == "ref:200"
        ]
        assert len(point_entries) == 1

        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ref_entries = [x for x in ledger if x.get("idempotency_key") == "ref:200"]
        assert len(ref_entries) == 1
    finally:
        tmp.cleanup()
