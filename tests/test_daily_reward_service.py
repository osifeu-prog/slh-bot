from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import core.daily_reward_service as daily_reward_service


TZ = ZoneInfo("Asia/Jerusalem")


def _db(points=100, credits=7):
    return {
        "users": {
            "123": {
                "name": "Test User",
                "wallet": {"credits": credits, "staked": 0},
                "gamification": {"points": points, "level": (points // 100) + 1},
                "points_ledger": [],
            }
        }
    }


def _use_db(monkeypatch, db):
    monkeypatch.setattr(
        daily_reward_service.state_manager,
        "atomic_update",
        lambda mutate: mutate(db),
    )
    monkeypatch.setattr(
        daily_reward_service.state_manager,
        "load_db",
        lambda: db,
    )


def _local(day, hour=12):
    return datetime.fromisoformat(f"{day}T{hour:02d}:00:00").replace(tzinfo=TZ)


def test_daily_claim_adds_points_once_and_does_not_mutate_credits_ledger(monkeypatch):
    db = _db()
    _use_db(monkeypatch, db)

    result = daily_reward_service.claim_daily_reward("123", now=_local("2026-10-15"))

    assert result["status"] == "claimed"
    assert result["points_awarded"] == 10
    assert result["streak"] == 1
    assert result["points_total"] == 110
    user = db["users"]["123"]
    assert user["wallet"]["credits"] == 7
    assert "ledger" not in db
    assert len(user["points_ledger"]) == 1
    event = user["points_ledger"][0]
    assert event["reason"] == "daily:claim"
    assert event["amount"] == 10
    assert event["meta"]["idempotency_key"] == "daily-points:123:2026-10-15"
    assert user["daily_rewards"]["last_claim_date"] == "2026-10-15"


def test_repeated_claim_same_local_date_never_awards_twice(monkeypatch):
    db = _db()
    _use_db(monkeypatch, db)

    first = daily_reward_service.claim_daily_reward("123", now=_local("2026-10-15", 8))
    second = daily_reward_service.claim_daily_reward("123", now=_local("2026-10-15", 22))

    assert first["status"] == "claimed"
    assert second["status"] == "already_claimed"
    assert second["points_awarded"] == 0
    assert db["users"]["123"]["gamification"]["points"] == 110
    assert len(db["users"]["123"]["points_ledger"]) == 1
    assert db["users"]["123"]["daily_rewards"]["total_claims"] == 1


def test_consecutive_local_days_increase_streak_and_missed_day_resets_it(monkeypatch):
    db = _db()
    _use_db(monkeypatch, db)

    first = daily_reward_service.claim_daily_reward("123", now=_local("2026-10-13"))
    second = daily_reward_service.claim_daily_reward("123", now=_local("2026-10-14"))
    third = daily_reward_service.claim_daily_reward("123", now=_local("2026-10-16"))

    assert (first["streak"], second["streak"], third["streak"]) == (1, 2, 1)
    assert db["users"]["123"]["gamification"]["points"] == 130
    assert len(db["users"]["123"]["points_ledger"]) == 3


def test_utc_timestamp_uses_israel_local_date_for_claim_key(monkeypatch):
    db = _db()
    _use_db(monkeypatch, db)
    utc_time = datetime(2026, 10, 15, 22, 30, tzinfo=timezone.utc)

    result = daily_reward_service.claim_daily_reward("123", now=utc_time)

    assert result["date"] == "2026-10-16"
    assert db["users"]["123"]["points_ledger"][0]["meta"]["idempotency_key"] == "daily-points:123:2026-10-16"


def test_existing_points_idempotency_key_repairs_daily_summary_without_double_award(monkeypatch):
    db = _db(points=110)
    db["users"]["123"]["points_ledger"].append({
        "time": "2026-10-15T09:00:00",
        "before": 100,
        "amount": 10,
        "after": 110,
        "reason": "daily:claim",
        "meta": {"idempotency_key": "daily-points:123:2026-10-15"},
    })
    _use_db(monkeypatch, db)

    result = daily_reward_service.claim_daily_reward("123", now=_local("2026-10-15"))

    assert result["status"] == "already_claimed"
    assert result["points_awarded"] == 0
    assert result["points_total"] == 110
    assert len(db["users"]["123"]["points_ledger"]) == 1
    assert db["users"]["123"]["daily_rewards"]["last_claim_date"] == "2026-10-15"


def test_unknown_user_is_not_created_or_rewarded(monkeypatch):
    db = {"users": {}}
    _use_db(monkeypatch, db)

    result = daily_reward_service.claim_daily_reward("123", now=_local("2026-10-15"))

    assert result["status"] == "user_not_found"
    assert result["points_awarded"] == 0
    assert db["users"] == {}


def test_daily_status_is_read_only(monkeypatch):
    db = _db()
    _use_db(monkeypatch, db)
    before = repr(db)

    result = daily_reward_service.get_daily_status("123", now=_local("2026-10-15"))

    assert result["status"] == "claim_available"
    assert result["daily_points"] == 10
    assert result["next_streak"] == 1
    assert repr(db) == before

def test_malformed_daily_state_fails_closed_without_overwriting_it(monkeypatch):
    db = _db()
    db["users"]["123"]["daily_rewards"] = ["unexpected", "state"]
    _use_db(monkeypatch, db)
    before = repr(db)

    try:
        daily_reward_service.claim_daily_reward("123", now=_local("2026-10-15"))
    except ValueError as exc:
        assert str(exc) == "DAILY_REWARD_STATE_INVALID"
    else:
        raise AssertionError("malformed daily state must fail closed")

    assert repr(db) == before
