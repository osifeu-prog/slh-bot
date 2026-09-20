"""Isolated regression tests for the internal Credits staking Alpha gate."""

import importlib
import tempfile
from pathlib import Path

import state_manager


def _seed_db(path):
    path.write_text(
        '{"users":{"123":{"wallet":{"credits":100.0,"staked":0.0}}},'
        '"stake_positions":{},"ledger":[]}',
        encoding="utf-8",
    )


def test_stake_and_unlock_round_trip_is_atomic():
    tmp = tempfile.TemporaryDirectory()
    try:
        db_path = Path(tmp.name) / "db.json"
        _seed_db(db_path)
        state_manager.DB_FILE = str(db_path)
        state_manager._LOCK_PATH = str(db_path) + ".lock"

        import core.staking_service as staking_service
        staking_service = importlib.reload(staking_service)

        first = staking_service.stake_locked(
            "123", 40, lock_days=1, meta={"source": "test"}
        )
        position_id = first["position"]["id"]

        assert first["credits"] == 60.0
        assert first["staked"] == 40.0
        assert first["position"]["status"] == "locked"

        db = state_manager.load_db()
        assert db["users"]["123"]["wallet"] == {"credits": 60.0, "staked": 40.0}
        assert db["stake_positions"][position_id]["uid"] == "123"

        try:
            staking_service.unstake_locked("123", position_id)
        except ValueError as exc:
            assert str(exc) == "still locked"
        else:
            raise AssertionError("locked position was released early")

        position = db["stake_positions"][position_id]
        position["unlocks_at"] = 0
        state_manager.atomic_update(
            lambda current: current["stake_positions"][position_id].update(
                {"unlocks_at": 0}
            ) or True
        )

        released = staking_service.unstake_locked(
            "123", position_id, meta={"source": "test"}
        )
        assert released["status"] == "unlocked"
        assert released["credits"] == 100.0
        assert released["staked"] == 0.0

        duplicate = staking_service.unstake_locked("123", position_id)
        assert duplicate["status"] == "duplicate"

        db = state_manager.load_db()
        assert db["users"]["123"]["wallet"] == {"credits": 100.0, "staked": 0.0}
        assert db["stake_positions"][position_id]["status"] == "unlocked"
        assert len(db["ledger"]) == 2
    finally:
        tmp.cleanup()
