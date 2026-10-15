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


def _restore_state_manager(db_file, lock_path):
    state_manager.DB_FILE = db_file
    state_manager._LOCK_PATH = lock_path


def test_referral_relationship_persists_once_and_does_not_repeat_reward():
    original_db_file = state_manager.DB_FILE
    original_lock_path = state_manager._LOCK_PATH
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
        _restore_state_manager(original_db_file, original_lock_path)
        tmp.cleanup()


def test_referral_full_reward_path_is_idempotent():
    original_db_file = state_manager.DB_FILE
    original_lock_path = state_manager._LOCK_PATH
    import core.reward_engine as reward_engine
    original_ledger = reward_engine.LEDGER
    tmp = tempfile.TemporaryDirectory()
    try:
        db_path = Path(tmp.name) / "db.json"
        ledger_path = Path(tmp.name) / "rewards_ledger.json"
        _seed_db(db_path)
        state_manager.DB_FILE = str(db_path)
        state_manager._LOCK_PATH = str(db_path) + ".lock"

        import handlers.join_handler as join_handler
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
            x for x in db["users"]["100"]["points_ledger"]
            if x.get("meta", {}).get("idempotency_key") == "ref:200"
        ]
        assert len(point_entries) == 1

        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ref_entries = [x for x in ledger if x.get("idempotency_key") == "ref:200"]
        assert len(ref_entries) == 1
    finally:
        reward_engine.LEDGER = original_ledger
        _restore_state_manager(original_db_file, original_lock_path)
        tmp.cleanup()


def test_persisted_referral_rewards_recover_after_partial_failure_without_double_pay():
    original_db_file = state_manager.DB_FILE
    original_lock_path = state_manager._LOCK_PATH
    import core.reward_engine as reward_engine
    original_ledger = reward_engine.LEDGER
    from core import referral_reward
    original_grant = referral_reward.grant
    tmp = tempfile.TemporaryDirectory()
    try:
        db_path = Path(tmp.name) / "db.json"
        ledger_path = Path(tmp.name) / "rewards_ledger.json"
        _seed_db(db_path)
        state_manager.DB_FILE = str(db_path)
        state_manager._LOCK_PATH = str(db_path) + ".lock"

        import handlers.join_handler as join_handler
        join_handler = importlib.reload(join_handler)
        reward_engine = importlib.reload(reward_engine)
        reward_engine.LEDGER = ledger_path

        assert join_handler._persist_referral("200", "100") is True
        failed = {"credits": False}

        def flaky_grant(*args, **kwargs):
            if kwargs.get("credits") == 0.9 and not failed["credits"]:
                failed["credits"] = True
                raise RuntimeError("simulated temporary credit ledger failure")
            return original_grant(*args, **kwargs)

        referral_reward.grant = flaky_grant
        try:
            try:
                referral_reward.settle_persisted_referral("200")
                assert False, "first attempt should surface the temporary failure"
            except RuntimeError:
                pass
        finally:
            referral_reward.grant = original_grant

        first_retry = referral_reward.settle_persisted_referral("200")
        assert first_retry["status"] == "SETTLED"
        second_retry = referral_reward.settle_persisted_referral("200")
        assert second_retry["status"] == "ALREADY_SETTLED"

        db = state_manager.load_db()
        referrer = db["users"]["100"]
        assert referrer["gamification"]["points"] == 10
        assert float(referrer["wallet"]["credits"]) == 0.9
        assert db["referral_reward_settlements"]["200"]["status"] == "settled"

        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        points_events = [x for x in ledger if x.get("idempotency_key") == "ref:200"]
        credit_events = [x for x in ledger if x.get("idempotency_key") == "referral-credit:200"]
        assert len(points_events) == 1
        assert len(credit_events) == 1
    finally:
        referral_reward.grant = original_grant
        reward_engine.LEDGER = original_ledger
        _restore_state_manager(original_db_file, original_lock_path)
        tmp.cleanup()


def test_parallel_persisted_referral_settlement_is_idempotent_and_awards_vip_once():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    original_db_file = state_manager.DB_FILE
    original_lock_path = state_manager._LOCK_PATH
    import core.reward_engine as reward_engine
    original_ledger = reward_engine.LEDGER
    from core import referral_reward
    original_settle = referral_reward.settle_successful_referral
    tmp = tempfile.TemporaryDirectory()
    try:
        db_path = Path(tmp.name) / "db.json"
        ledger_path = Path(tmp.name) / "rewards_ledger.json"
        _seed_db(db_path)
        seeded = json.loads(db_path.read_text(encoding="utf-8"))
        seeded["users"]["100"]["referral"]["count"] = 4
        seeded["users"]["100"]["wallet"] = {"credits": 0}
        db_path.write_text(json.dumps(seeded), encoding="utf-8")
        state_manager.DB_FILE = str(db_path)
        state_manager._LOCK_PATH = str(db_path) + ".lock"

        import handlers.join_handler as join_handler
        join_handler = importlib.reload(join_handler)
        reward_engine = importlib.reload(reward_engine)
        reward_engine.LEDGER = ledger_path

        assert join_handler._persist_referral("200", "100") is True
        barrier = Barrier(2)

        def synchronized_settle(referrer_uid, referred_uid):
            # Ensure both workers passed the initial settlement-marker check.
            barrier.wait(timeout=5)
            return original_settle(referrer_uid, referred_uid)

        referral_reward.settle_successful_referral = synchronized_settle
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [
                    pool.submit(referral_reward.settle_persisted_referral, "200"),
                    pool.submit(referral_reward.settle_persisted_referral, "200"),
                ]
                results = [future.result(timeout=10) for future in futures]
        finally:
            referral_reward.settle_successful_referral = original_settle

        db = state_manager.load_db()
        referrer = db["users"]["100"]
        assert referrer["gamification"]["points"] == 10
        assert float(referrer["wallet"]["credits"]) == 0.9
        point_events = [
            x for x in referrer.get("points_ledger", [])
            if x.get("meta", {}).get("idempotency_key") == "ref:200"
        ]
        assert len(point_events) == 1
        credit_events = [
            x for x in db.get("ledger", [])
            if (x.get("meta") or {}).get("idempotency_key") == "referral-credit:200"
        ]
        assert len(credit_events) == 1
        assert len(db.get("referral_vip_awards", {})) == 1
        assert db["referral_vip_awards"]["100"]["source"] == "referral_milestone"
        assert all(result["status"] in {"SETTLED", "ALREADY_SETTLED"} for result in results)
        assert db["referral_reward_settlements"]["200"]["status"] == "settled"
    finally:
        referral_reward.settle_successful_referral = original_settle
        reward_engine.LEDGER = original_ledger
        _restore_state_manager(original_db_file, original_lock_path)
        tmp.cleanup()
