from copy import deepcopy
from unittest import mock

import state_manager
from core import referral_attribution


def _db():
    return {
        "users": {
            "100": {"name": "Referrer", "referral": {"count": 0}},
            "300": {"name": "Existing", "joined": True, "referral": {"referred_by": "100"}},
        },
        "pending_referrals": {},
        "referral_start_events": {},
    }


def _patch_db(monkeypatch, db):
    monkeypatch.setattr(state_manager, "load_db", lambda: db)

    def atomic_update(mutate):
        return mutate(db)

    monkeypatch.setattr(state_manager, "atomic_update", atomic_update)


def test_referral_start_is_recorded_once_without_awarding_success(monkeypatch):
    db = _db()
    _patch_db(monkeypatch, db)

    first = referral_attribution.record_referral_start(
        "200", "100", is_new_user=True, now="2026-10-10T10:00:00+00:00"
    )
    again = referral_attribution.record_referral_start(
        "200", "100", is_new_user=True, now="2026-10-10T10:05:00+00:00"
    )

    assert first["status"] == "PENDING_JOIN"
    assert again["already_recorded"] is True
    assert db["referral_start_events"]["200"]["first_seen_at"] == "2026-10-10T10:00:00+00:00"
    assert db["users"]["100"]["referral"]["count"] == 0
    assert db["pending_referrals"]["200"] == "100"


def test_first_referrer_wins_and_repeat_start_cannot_reassign_attribution(monkeypatch):
    db = _db()
    db["users"]["101"] = {"name": "Other Referrer", "referral": {"count": 0}}
    _patch_db(monkeypatch, db)

    first = referral_attribution.record_referral_start(
        "200", "100", is_new_user=True, now="2026-10-10T10:00:00+00:00"
    )
    second = referral_attribution.record_referral_start(
        "200", "101", is_new_user=True, now="2026-10-10T10:10:00+00:00"
    )

    assert first["referrer_uid"] == "100"
    assert second["already_recorded"] is True
    assert db["pending_referrals"]["200"] == "100"
    assert db["referral_start_events"]["200"]["referrer_uid"] == "100"


def test_existing_account_start_is_analytics_only_and_never_awards(monkeypatch):
    db = _db()
    original = deepcopy(db["users"]["100"]["referral"])
    _patch_db(monkeypatch, db)

    result = referral_attribution.record_referral_start(
        "300", "100", is_new_user=False, now="2026-10-10T10:00:00+00:00"
    )

    assert result["status"] == "EXISTING_USER"
    assert "300" not in db["pending_referrals"]
    assert db["users"]["100"]["referral"] == original
    assert db["referral_start_events"]["300"]["status"] == "EXISTING_USER"


def test_join_completion_marks_pending_referral_converted_once(monkeypatch):
    db = _db()
    _patch_db(monkeypatch, db)
    referral_attribution.record_referral_start(
        "200", "100", is_new_user=True, now="2026-10-10T10:00:00+00:00"
    )
    # The canonical join flow has already persisted the user profile at this point.
    db["users"]["200"] = {"name": "New User", "joined": True}

    first = referral_attribution.mark_join_completed(
        "200", now="2026-10-10T11:00:00+00:00"
    )
    second = referral_attribution.mark_join_completed(
        "200", now="2026-10-10T12:00:00+00:00"
    )

    assert first["status"] == "CONVERTED"
    assert second["joined_at"] == "2026-10-10T11:00:00+00:00"
    assert db["users"]["200"]["joined_at"] == "2026-10-10T11:00:00+00:00"
    assert db["referral_start_events"]["200"]["status"] == "CONVERTED"
    assert db["users"]["100"]["referral"]["count"] == 0


def test_referral_stats_are_aggregate_only(monkeypatch):
    db = _db()
    db["referral_start_events"] = {
        "200": {"referrer_uid": "100", "status": "PENDING_JOIN"},
        "201": {"referrer_uid": "100", "status": "CONVERTED"},
        "202": {"referrer_uid": "100", "status": "EXISTING_USER"},
        "203": {"referrer_uid": "999", "status": "PENDING_JOIN"},
    }
    _patch_db(monkeypatch, db)

    result = referral_attribution.referral_start_stats("100")

    assert result == {
        "unique_starts": 3,
        "pending_joins": 1,
        "converted_joins": 1,
        "existing_user_starts": 1,
    }
    assert all(not isinstance(value, list) for value in result.values())


def test_invalid_or_self_referral_is_ignored_without_mutation(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_db(monkeypatch, db)

    result = referral_attribution.record_referral_start(
        "100", "100", is_new_user=True, now="2026-10-10T10:00:00+00:00"
    )

    assert result["recorded"] is False
    assert db == before
