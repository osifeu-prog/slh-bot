"""Failure recovery and exactly-once referral reward settlement tests."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import state_manager
from core import economy_bridge
from core import referral_reward
from core import reward_engine


def _seed(path):
    path.write_text(
        json.dumps(
            {
                "users": {
                    "100": {
                        "joined": True,
                        "wallet": {"credits": 0.0},
                        "gamification": {"points": 0, "level": 1},
                        "points_ledger": [],
                        "referral": {"count": 1},
                    },
                    "200": {
                        "joined": True,
                        "wallet": {"credits": 0.0},
                        "gamification": {"points": 0, "level": 1},
                        "points_ledger": [],
                        "referral": {
                            "referred_by": "100",
                            "referred_at": "2026-10-15T12:00:00+00:00",
                        },
                    },
                },
                "pending_referrals": {"200": "100"},
                "ledger": [],
            }
        ),
        encoding="utf-8",
    )


def _configure_state(monkeypatch, tmp_path):
    db_path = tmp_path / "db.json"
    rewards_path = tmp_path / "rewards_ledger.json"
    _seed(db_path)
    monkeypatch.setattr(state_manager, "DB_FILE", str(db_path))
    monkeypatch.setattr(state_manager, "_LOCK_PATH", str(db_path) + ".lock")
    monkeypatch.setattr(reward_engine, "LEDGER", rewards_path)
    return db_path, rewards_path


def _assert_exactly_once(db_path):
    db = json.loads(db_path.read_text(encoding="utf-8"))
    referrer = db["users"]["100"]
    assert referrer["wallet"]["credits"] == 0.9
    assert referrer["gamification"]["points"] == 10

    points = [
        row for row in referrer["points_ledger"]
        if row.get("meta", {}).get("idempotency_key") == "ref:200"
    ]
    credits = [
        row for row in db["ledger"]
        if row.get("meta", {}).get("idempotency_key") == "referral-credit:200"
    ]
    assert len(points) == 1
    assert points[0]["reason"] == "referral"
    assert points[0]["amount"] == 10
    assert len(credits) == 1
    assert credits[0]["reason"] == "referral_success_bonus"
    assert credits[0]["amount"] == 0.9
    assert db["users"]["100"]["referral"]["count"] == 1
    assert db["users"]["200"]["referral"]["referred_by"] == "100"
    assert "200" not in db.get("pending_referrals", {})
    assert db["referral_reward_settlements"]["200"]["status"] == "SETTLED"


def test_partial_reward_failure_after_credit_commit_recovers_without_double_pay(monkeypatch, tmp_path):
    db_path, rewards_path = _configure_state(monkeypatch, tmp_path)
    real_add_credits = economy_bridge.add_credits
    calls = {"count": 0}

    def commit_then_raise_once(uid, amount, reason="bridge:add_credits", meta=None):
        result = real_add_credits(uid, amount, reason=reason, meta=meta)
        calls["count"] += 1
        if calls["count"] == 1:
            # Simulate a lost response after the canonical transaction committed.
            raise RuntimeError("simulated response loss after commit")
        return result

    monkeypatch.setattr(economy_bridge, "add_credits", commit_then_raise_once)

    try:
        referral_reward.recover_persisted_referral("200")
    except RuntimeError as exc:
        assert "simulated response loss" in str(exc)
    else:
        raise AssertionError("the simulated first-attempt failure should propagate")

    partial = json.loads(db_path.read_text(encoding="utf-8"))
    assert partial["users"]["100"]["wallet"]["credits"] == 0.9
    assert partial["users"]["100"]["gamification"]["points"] == 10
    assert "200" not in partial.get("referral_reward_settlements", {})
    assert partial["pending_referrals"]["200"] == "100"

    result = referral_reward.recover_persisted_referral("200")
    assert result["status"] == "SETTLED"
    _assert_exactly_once(db_path)

    again = referral_reward.recover_persisted_referral("200")
    assert again["status"] == "ALREADY_SETTLED"
    _assert_exactly_once(db_path)

    reward_ledger = json.loads(rewards_path.read_text(encoding="utf-8"))
    assert sum(row.get("idempotency_key") == "ref:200" for row in reward_ledger) == 1
    assert sum(row.get("idempotency_key") == "referral-credit:200" for row in reward_ledger) == 1


def test_concurrent_recovery_calls_award_each_reward_once(monkeypatch, tmp_path):
    db_path, _rewards_path = _configure_state(monkeypatch, tmp_path)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(referral_reward.recover_persisted_referral, ["200", "200"]))

    assert {result["status"] for result in results} == {"SETTLED", "ALREADY_SETTLED"}
    _assert_exactly_once(db_path)


def test_recovery_never_invents_or_reassigns_referral(monkeypatch, tmp_path):
    db_path, _rewards_path = _configure_state(monkeypatch, tmp_path)
    db = json.loads(db_path.read_text(encoding="utf-8"))
    db["users"]["200"]["referral"].pop("referred_by")
    db["pending_referrals"]["200"] = "100"
    db_path.write_text(json.dumps(db), encoding="utf-8")

    result = referral_reward.recover_persisted_referral("200")

    assert result["status"] == "NO_PERSISTED_REFERRAL"
    unchanged = json.loads(db_path.read_text(encoding="utf-8"))
    assert unchanged["users"]["100"]["wallet"]["credits"] == 0.0
    assert unchanged["users"]["100"]["gamification"]["points"] == 0
    assert unchanged["pending_referrals"]["200"] == "100"



def test_missing_credit_leg_recovers_after_precommit_failure(monkeypatch, tmp_path):
    """A failed Credits leg must retry without issuing the already-awarded Points again."""
    db_path, rewards_path = _configure_state(monkeypatch, tmp_path)
    real_add_credits = economy_bridge.add_credits
    calls = {"count": 0}

    def fail_before_commit_once(uid, amount, reason="bridge:add_credits", meta=None):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("simulated Credits failure before commit")
        return real_add_credits(uid, amount, reason=reason, meta=meta)

    monkeypatch.setattr(economy_bridge, "add_credits", fail_before_commit_once)

    try:
        referral_reward.recover_persisted_referral("200")
    except RuntimeError as exc:
        assert "before commit" in str(exc)
    else:
        raise AssertionError("the simulated first Credits failure should propagate")

    partial = json.loads(db_path.read_text(encoding="utf-8"))
    assert partial["users"]["100"]["wallet"]["credits"] == 0.0
    assert partial["users"]["100"]["gamification"]["points"] == 10
    assert sum(
        row.get("meta", {}).get("idempotency_key") == "ref:200"
        for row in partial["users"]["100"]["points_ledger"]
    ) == 1
    assert not any(
        row.get("meta", {}).get("idempotency_key") == "referral-credit:200"
        for row in partial["ledger"]
    )
    assert "200" not in partial.get("referral_reward_settlements", {})
    assert partial["pending_referrals"]["200"] == "100"

    result = referral_reward.recover_persisted_referral("200")
    assert result["status"] == "SETTLED"
    _assert_exactly_once(db_path)

    again = referral_reward.recover_persisted_referral("200")
    assert again["status"] == "ALREADY_SETTLED"
    _assert_exactly_once(db_path)

    reward_ledger = json.loads(rewards_path.read_text(encoding="utf-8"))
    assert sum(row.get("idempotency_key") == "ref:200" for row in reward_ledger) == 1
    assert sum(row.get("idempotency_key") == "referral-credit:200" for row in reward_ledger) == 1
