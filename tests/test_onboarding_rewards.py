"""Tests for idempotent, eligibility-gated onboarding Credits."""
import json
from pathlib import Path

import state_manager
from core import onboarding_rewards


def _sandbox(tmp_path, monkeypatch, user=None):
    path = tmp_path / "db.json"
    db = {
        "users": {
            "100": user or {
                "joined": True,
                "academy": {"courses": {"bitcoin_mastery": {"stage": 0, "completed": []}}},
                "wallet": {"credits": 0.0, "staked": 0},
            }
        },
        "ledger": [],
    }
    path.write_text(json.dumps(db), encoding="utf-8")
    monkeypatch.setattr(state_manager, "DB_FILE", str(path))
    monkeypatch.setattr(state_manager, "_LOCK_PATH", str(path) + ".lock")
    return path


def _state(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_unjoined_or_uninitialized_user_cannot_get_signup_bonus(tmp_path, monkeypatch):
    path = _sandbox(tmp_path, monkeypatch, {
        "joined": True,
        "academy": {"courses": {}},
        "wallet": {"credits": 0.0},
    })

    marker = onboarding_rewards.mark_signup_bonus_pending("100")
    result = onboarding_rewards.grant_signup_bonus("100")

    assert marker == {"status": "BLOCKED", "reason": "ONBOARDING_NOT_COMPLETE"}
    assert result == {"status": "BLOCKED", "reason": "ONBOARDING_NOT_COMPLETE"}
    assert _state(path)["ledger"] == []
    assert "onboarding_signup_bonus_status" not in _state(path)["users"]["100"]


def test_signup_bonus_is_applied_once_and_uses_canonical_ledger(tmp_path, monkeypatch):
    path = _sandbox(tmp_path, monkeypatch)

    assert onboarding_rewards.mark_signup_bonus_pending("100")["status"] == "PENDING"
    first = onboarding_rewards.grant_signup_bonus("100")
    second = onboarding_rewards.grant_signup_bonus("100")

    db = _state(path)
    rows = [
        row for row in db["ledger"]
        if (row.get("meta") or {}).get("idempotency_key")
        == "onboarding-signup-credits:v1:100"
    ]
    assert first["status"] == "GRANTED"
    assert first["credits_awarded"] == 5
    assert second["status"] == "ALREADY_AWARDED"
    assert db["users"]["100"]["wallet"]["credits"] == 5
    assert db["users"]["100"]["onboarding_signup_bonus_status"] == "AWARDED"
    assert len(rows) == 1
    assert rows[0]["reason"] == "onboarding:signup_bonus"
    assert rows[0]["before"] == 0
    assert rows[0]["amount"] == 5
    assert rows[0]["after"] == 5


def test_retry_recovers_after_credit_transaction_but_before_marker_finalize(tmp_path, monkeypatch):
    path = _sandbox(tmp_path, monkeypatch)
    onboarding_rewards.mark_signup_bonus_pending("100")
    key = "onboarding-signup-credits:v1:100"

    from core.economy_service import record_transaction
    first = record_transaction(
        "100", 5, "onboarding:signup_bonus",
        {"source": "completed_join_onboarding", "idempotency_key": key},
        return_details=True,
    )
    assert first["status"] == "APPLIED"
    assert _state(path)["users"]["100"]["onboarding_signup_bonus_status"] == "PENDING"

    recovered = onboarding_rewards.grant_signup_bonus("100")
    db = _state(path)
    rows = [r for r in db["ledger"] if (r.get("meta") or {}).get("idempotency_key") == key]

    assert recovered["status"] == "DUPLICATE"
    assert db["users"]["100"]["wallet"]["credits"] == 5
    assert db["users"]["100"]["onboarding_signup_bonus_status"] == "AWARDED"
    assert len(rows) == 1


def test_idempotency_key_conflict_blocks_without_minting_extra_credits(tmp_path, monkeypatch):
    path = _sandbox(tmp_path, monkeypatch)
    onboarding_rewards.mark_signup_bonus_pending("100")
    from core.economy_service import record_transaction

    record_transaction(
        "100", 3, "different:reason",
        {"idempotency_key": "onboarding-signup-credits:v1:100"},
    )
    before = _state(path)["users"]["100"]["wallet"]["credits"]

    result = onboarding_rewards.grant_signup_bonus("100")
    db = _state(path)

    assert result == {"status": "BLOCKED", "reason": "TRANSACTION_CONFLICT"}
    assert db["users"]["100"]["wallet"]["credits"] == before == 3
    assert db["users"]["100"]["onboarding_signup_bonus_status"] == "PENDING"
    assert len(db["ledger"]) == 1


def test_existing_user_is_not_automatically_marked_as_signup_eligible(tmp_path, monkeypatch):
    path = _sandbox(tmp_path, monkeypatch)
    result = onboarding_rewards.grant_signup_bonus("100")
    db = _state(path)

    assert result == {"status": "NOT_PENDING"}
    assert db["users"]["100"]["wallet"]["credits"] == 0
    assert db["ledger"] == []
